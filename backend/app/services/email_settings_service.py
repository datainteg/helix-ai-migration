"""Email settings service — per-org SMTP / SendGrid config + test send.

CRUD over the EmailSettings row, plus `resolve_email_config` (DB row preferred,
.env fallback) used by email_service, and `send_test_email` which sends a real
message using an explicit (possibly unsaved) config so admins can verify before
saving.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_settings import EmailSettings
from app.services.secret_service import encrypt_value, decrypt_value, mask_key

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    enabled: bool
    provider: str          # "smtp" | "sendgrid"
    from_email: str
    from_name: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_tls: bool
    sendgrid_api_key: str
    source: str            # "db" | "env"


def get_settings_row(db: Session, organization_id: str) -> Optional[EmailSettings]:
    return db.query(EmailSettings).filter(EmailSettings.organization_id == organization_id).first()


def to_public_dict(row: Optional[EmailSettings]) -> dict:
    """Serialise for the API — secrets are masked, never returned in clear."""
    if not row:
        return {
            "configured": False,
            "enabled": False,
            "provider": "smtp",
            "from_email": settings.EMAIL_FROM or "",
            "from_name": settings.EMAIL_FROM_NAME or "",
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password_set": False,
            "smtp_tls": True,
            "sendgrid_api_key_set": False,
        }
    return {
        "configured": True,
        "enabled": row.enabled,
        "provider": row.provider,
        "from_email": row.from_email or "",
        "from_name": row.from_name or "",
        "smtp_host": row.smtp_host or "",
        "smtp_port": row.smtp_port,
        "smtp_user": row.smtp_user or "",
        "smtp_password_set": bool(row.smtp_password_enc),
        "smtp_tls": row.smtp_tls,
        "sendgrid_api_key_set": bool(row.sendgrid_api_key_enc),
    }


def upsert_settings(db: Session, organization_id: str, data: dict) -> EmailSettings:
    """Create/update the org's email settings.

    Secret fields (smtp_password, sendgrid_api_key) are only written when a
    non-empty value is supplied, so an admin saving the form without retyping
    the password keeps the stored one.
    """
    row = get_settings_row(db, organization_id)
    if row is None:
        row = EmailSettings(organization_id=organization_id)
        db.add(row)

    row.enabled = bool(data.get("enabled", row.enabled))
    row.provider = data.get("provider", row.provider) or "smtp"
    row.from_email = data.get("from_email", row.from_email)
    row.from_name = data.get("from_name", row.from_name)
    row.smtp_host = data.get("smtp_host", row.smtp_host)
    if data.get("smtp_port") is not None:
        row.smtp_port = int(data["smtp_port"])
    row.smtp_user = data.get("smtp_user", row.smtp_user)
    if data.get("smtp_tls") is not None:
        row.smtp_tls = bool(data["smtp_tls"])

    pwd = data.get("smtp_password")
    if pwd:  # only overwrite when provided
        row.smtp_password_enc = encrypt_value(pwd)
    api_key = data.get("sendgrid_api_key")
    if api_key:
        row.sendgrid_api_key_enc = encrypt_value(api_key)

    db.commit()
    db.refresh(row)
    return row


def _config_from_row(row: EmailSettings) -> EmailConfig:
    return EmailConfig(
        enabled=row.enabled,
        provider=row.provider or "smtp",
        from_email=row.from_email or settings.EMAIL_FROM,
        from_name=row.from_name or settings.EMAIL_FROM_NAME,
        smtp_host=row.smtp_host or "",
        smtp_port=row.smtp_port or 587,
        smtp_user=row.smtp_user or "",
        smtp_password=decrypt_value(row.smtp_password_enc) if row.smtp_password_enc else "",
        smtp_tls=row.smtp_tls,
        sendgrid_api_key=decrypt_value(row.sendgrid_api_key_enc) if row.sendgrid_api_key_enc else "",
        source="db",
    )


def _config_from_env() -> EmailConfig:
    return EmailConfig(
        enabled=settings.EMAIL_ENABLED,
        provider="sendgrid" if settings.SENDGRID_API_KEY else "smtp",
        from_email=settings.EMAIL_FROM,
        from_name=settings.EMAIL_FROM_NAME,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_user=settings.SMTP_USER,
        smtp_password=settings.SMTP_PASSWORD,
        smtp_tls=settings.SMTP_TLS,
        sendgrid_api_key=settings.SENDGRID_API_KEY,
        source="env",
    )


def resolve_email_config(db: Session, organization_id: Optional[str]) -> EmailConfig:
    """Effective email config: a configured DB row wins, else the .env config."""
    if organization_id:
        row = get_settings_row(db, organization_id)
        if row and (row.smtp_host or row.sendgrid_api_key_enc):
            return _config_from_row(row)
    return _config_from_env()


async def send_with_config(cfg: EmailConfig, *, to: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    """Send an email using an explicit config (used by both the live send path
    and the admin test action)."""
    if cfg.provider == "sendgrid" and cfg.sendgrid_api_key:
        import httpx
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": cfg.from_email, "name": cfg.from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {cfg.sendgrid_api_key}"},
                json=payload, timeout=15,
            )
        if res.status_code not in (200, 202):
            raise RuntimeError(f"SendGrid error {res.status_code}: {res.text[:200]}")
        return

    # SMTP
    import aiosmtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not cfg.smtp_host:
        raise RuntimeError("SMTP host is not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg.from_name} <{cfg.from_email}>"
    msg["To"] = to
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # TLS mode depends on the port:
    #   465 → implicit SSL (wrap the socket on connect; use_tls=True)
    #   587/25 → STARTTLS (connect plaintext, then upgrade; start_tls=True)
    # The old code always used start_tls, so port 465 hung waiting for a
    # plaintext greeting that never comes ("Timed out waiting for server ready").
    if cfg.smtp_port == 465:
        use_tls, start_tls = True, False
    else:
        use_tls, start_tls = False, bool(cfg.smtp_tls)

    await aiosmtplib.send(
        msg,
        hostname=cfg.smtp_host,
        port=cfg.smtp_port,
        username=cfg.smtp_user or None,
        password=cfg.smtp_password or None,
        use_tls=use_tls,
        start_tls=start_tls,
        timeout=15,
    )


def build_test_config(db: Session, organization_id: str, overrides: dict) -> EmailConfig:
    """Config for a test send: start from the saved row (or env), then apply any
    overrides the admin typed in the form (so they can test before saving). A
    blank secret override falls back to the stored secret."""
    base = resolve_email_config(db, organization_id)
    provider = overrides.get("provider") or base.provider
    return EmailConfig(
        enabled=True,
        provider=provider,
        from_email=overrides.get("from_email") or base.from_email,
        from_name=overrides.get("from_name") or base.from_name,
        smtp_host=overrides.get("smtp_host") or base.smtp_host,
        smtp_port=int(overrides["smtp_port"]) if overrides.get("smtp_port") else base.smtp_port,
        smtp_user=overrides.get("smtp_user") if overrides.get("smtp_user") is not None else base.smtp_user,
        smtp_password=overrides.get("smtp_password") or base.smtp_password,
        smtp_tls=overrides["smtp_tls"] if overrides.get("smtp_tls") is not None else base.smtp_tls,
        sendgrid_api_key=overrides.get("sendgrid_api_key") or base.sendgrid_api_key,
        source="test",
    )
