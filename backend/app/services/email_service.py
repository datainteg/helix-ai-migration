"""Email delivery service — SMTP (aiosmtplib) or SendGrid HTTP fallback.

Usage:
    await send_email(to="user@example.com", subject="...", html_body="...")

If EMAIL_ENABLED=false (default), logs the email instead of sending it.
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(*, to: str, subject: str, html_body: str, text_body: str | None = None,
                     db=None, organization_id: str | None = None) -> None:
    """Send an email.

    When a `db` session is supplied, the org's admin-configured email settings
    (DB row) are preferred over the .env config; otherwise the .env config is
    used. This keeps existing call sites working while letting admins configure
    SMTP from the UI.
    """
    # Prefer DB-backed config when we have a session + org.
    if db is not None and organization_id is not None:
        try:
            from app.services.email_settings_service import resolve_email_config, send_with_config
            cfg = resolve_email_config(db, organization_id)
            if not cfg.enabled or (not cfg.smtp_host and not cfg.sendgrid_api_key):
                logger.info("EMAIL_DISABLED (org=%s) to=%s subject=%s", organization_id, to, subject)
                return
            await send_with_config(cfg, to=to, subject=subject, html_body=html_body, text_body=text_body)
            return
        except Exception:
            logger.exception("DB email config send failed; falling back to env config")

    # Env-based fallback (original behaviour).
    if not settings.EMAIL_ENABLED:
        logger.info("EMAIL_DISABLED to=%s subject=%s", to, subject)
        return

    if settings.SENDGRID_API_KEY:
        await _send_sendgrid(to=to, subject=subject, html_body=html_body, text_body=text_body)
    else:
        await _send_smtp(to=to, subject=subject, html_body=html_body, text_body=text_body)


async def _send_sendgrid(*, to: str, subject: str, html_body: str, text_body: str | None) -> None:
    import httpx

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.EMAIL_FROM, "name": settings.EMAIL_FROM_NAME},
        "subject": subject,
        "content": [
            {"type": "text/html", "value": html_body},
        ],
    }
    if text_body:
        payload["content"].insert(0, {"type": "text/plain", "value": text_body})

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
            json=payload,
            timeout=15,
        )
    if res.status_code not in (200, 202):
        logger.error("SendGrid delivery failed status=%s body=%s", res.status_code, res.text[:200])
    else:
        logger.info("SendGrid email sent to=%s subject=%s", to, subject)


async def _send_smtp(*, to: str, subject: str, html_body: str, text_body: str | None) -> None:
    import aiosmtplib

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"] = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=False,
        start_tls=settings.SMTP_TLS,
    )
    logger.info("SMTP email sent to=%s subject=%s", to, subject)


# ── Email templates ───────────────────────────────────────────────────────────

def render_password_reset_email(reset_url: str, expiry_minutes: int = 30) -> tuple[str, str]:
    """Returns (subject, html_body) for password reset email."""
    subject = f"[{settings.APP_NAME}] Reset your password"
    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#1d4ed8">{settings.APP_NAME}</h2>
      <p>Someone requested a password reset for your account.</p>
      <p style="margin:24px 0">
        <a href="{reset_url}" style="background:#1d4ed8;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block">
          Reset Password
        </a>
      </p>
      <p style="color:#6b7280;font-size:14px">Link expires in {expiry_minutes} minutes.</p>
      <p style="color:#6b7280;font-size:14px">If you didn't request this, ignore this email.</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
      <p style="color:#9ca3af;font-size:12px">{settings.APP_NAME} — Open-source AI Migration Platform</p>
    </body></html>
    """
    return subject, html


def render_invitation_email(inviter_name: str, org_name: str, invite_url: str) -> tuple[str, str]:
    """Returns (subject, html_body) for org invitation email."""
    subject = f"[{settings.APP_NAME}] {inviter_name} invited you to {org_name}"
    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#1d4ed8">{settings.APP_NAME}</h2>
      <p><strong>{inviter_name}</strong> has invited you to join <strong>{org_name}</strong>.</p>
      <p style="margin:24px 0">
        <a href="{invite_url}" style="background:#1d4ed8;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block">
          Accept Invitation
        </a>
      </p>
      <p style="color:#6b7280;font-size:14px">This invitation expires in 7 days.</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
      <p style="color:#9ca3af;font-size:12px">{settings.APP_NAME} — Open-source AI Migration Platform</p>
    </body></html>
    """
    return subject, html


def render_workflow_complete_email(project_name: str, workflow_id: str, status: str, dashboard_url: str) -> tuple[str, str]:
    """Returns (subject, html_body) for workflow completion notification."""
    emoji = "✅" if status == "completed" else "❌"
    subject = f"[{settings.APP_NAME}] {emoji} Workflow {status}: {project_name}"
    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#1d4ed8">{settings.APP_NAME}</h2>
      <p>Your BMAD planning workflow for <strong>{project_name}</strong> has <strong>{status}</strong>.</p>
      <p style="color:#6b7280;font-size:14px">Workflow ID: <code>{workflow_id}</code></p>
      <p style="margin:24px 0">
        <a href="{dashboard_url}" style="background:#1d4ed8;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block">
          View Results
        </a>
      </p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
      <p style="color:#9ca3af;font-size:12px">{settings.APP_NAME}</p>
    </body></html>
    """
    return subject, html
