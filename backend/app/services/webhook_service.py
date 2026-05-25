"""Webhook delivery service.

Delivers POST requests to registered endpoints with HMAC-SHA256 signature.
Header: X-Helix-Signature: sha256=<hex>
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.security.ssrf import SSRFViolation, validate_external_url

logger = logging.getLogger(__name__)


def _sign_payload(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def deliver_webhook(db: Session, org_id: str, event: str, payload: dict) -> None:
    """Fire webhook to all active matching endpoints for the org."""
    endpoints = (
        db.query(WebhookEndpoint)
        .filter(WebhookEndpoint.organization_id == org_id, WebhookEndpoint.is_active == True)
        .all()
    )

    body = json.dumps({"event": event, "data": payload, "timestamp": datetime.now(timezone.utc).isoformat()}).encode()

    async with httpx.AsyncClient(timeout=10) as client:
        for ep in endpoints:
            events_list = [e.strip() for e in ep.events.split(",")]
            if "*" not in events_list and event not in events_list:
                continue

            headers = {"Content-Type": "application/json", "X-Helix-Event": event}
            if ep.secret:
                # Decrypt the stored Fernet ciphertext; fall back to the raw
                # value to keep pre-encryption rows working through migration.
                from app.services.secret_service import decrypt_value
                try:
                    signing_secret = decrypt_value(ep.secret)
                except Exception:  # noqa: BLE001
                    signing_secret = ep.secret
                headers["X-Helix-Signature"] = _sign_payload(signing_secret, body)

            delivery = WebhookDelivery(
                endpoint_id=ep.id,
                event=event,
                payload=body.decode(),
            )
            db.add(delivery)
            db.flush()

            # Re-validate URL at delivery — admit-time check may have been
            # bypassed if the row was inserted directly into the DB.
            try:
                validate_external_url(ep.url)
            except SSRFViolation as exc:
                delivery.success = False
                delivery.error = f"ssrf_block: {exc}"[:255]
                logger.warning("webhook_ssrf_block event=%s url=%s err=%s", event, ep.url, exc)
                db.commit()
                continue

            try:
                res = await client.post(ep.url, content=body, headers=headers)
                delivery.status_code = str(res.status_code)
                delivery.response_body = res.text[:500]
                delivery.success = 200 <= res.status_code < 300
                logger.info("webhook_delivered event=%s url=%s status=%s", event, ep.url, res.status_code)
            except Exception as exc:
                delivery.success = False
                delivery.error = str(exc)[:255]
                logger.warning("webhook_failed event=%s url=%s err=%s", event, ep.url, exc)

            db.commit()
