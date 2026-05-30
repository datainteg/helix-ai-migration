"""Notification service — emit + read in-app notifications, with optional email.

`emit()` is the single entry point used by the cost-enforcement path and the
workflow-result path. It honours the org's NotificationRule (enabled / threshold
/ channels), dedupes repeating events, and optionally sends an email through the
existing email_service.

Design notes:
- Emit is best-effort: callers wrap it so a notification failure never breaks
  the action that triggered it.
- `defer_commit=True` lets the emit ride the caller's transaction (used on the
  worker hot path) — the caller commits.
- Email is fired best-effort and non-blocking; if there's no running event loop
  (sync worker context) we skip email rather than block the request.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationRule

logger = logging.getLogger(__name__)

# How long a dedupe_key suppresses repeat emits.
_DEDUPE_WINDOW = timedelta(hours=6)

# Default rule set — used when an org hasn't customised a rule yet. Keys are
# event types; threshold is the "approaching" ratio for cost events.
_DEFAULT_RULES: dict[str, dict] = {
    "cost.cap_approaching": {"enabled": True, "threshold": 0.8, "channels": "in_app"},
    "cost.cap_breached": {"enabled": True, "threshold": None, "channels": "in_app"},
    "budget.cap_breached": {"enabled": True, "threshold": None, "channels": "in_app"},
    "workflow.failed": {"enabled": True, "threshold": None, "channels": "in_app"},
    "approval.pending": {"enabled": True, "threshold": None, "channels": "in_app"},
}


def get_rule(db: Session, organization_id: str, event_type: str) -> dict:
    """Effective rule for an event: the org's row, or the built-in default."""
    row = (
        db.query(NotificationRule)
        .filter(NotificationRule.organization_id == organization_id, NotificationRule.event_type == event_type)
        .first()
    )
    if row:
        return {"enabled": row.enabled, "threshold": row.threshold, "channels": row.channels}
    return _DEFAULT_RULES.get(event_type, {"enabled": True, "threshold": None, "channels": "in_app"})


def list_rules(db: Session, organization_id: str) -> list[dict]:
    """All known event types with their effective config (org override or default)."""
    out = []
    for event_type in _DEFAULT_RULES:
        r = get_rule(db, organization_id, event_type)
        out.append({"event_type": event_type, **r})
    return out


def upsert_rule(db: Session, organization_id: str, event_type: str, *, enabled: bool,
                threshold: Optional[float], channels: str) -> dict:
    row = (
        db.query(NotificationRule)
        .filter(NotificationRule.organization_id == organization_id, NotificationRule.event_type == event_type)
        .first()
    )
    if row is None:
        row = NotificationRule(organization_id=organization_id, event_type=event_type)
        db.add(row)
    row.enabled = enabled
    row.threshold = threshold
    row.channels = channels
    db.commit()
    db.refresh(row)
    return {"event_type": row.event_type, "enabled": row.enabled, "threshold": row.threshold, "channels": row.channels}


def emit(
    db: Session,
    *,
    org_id: str,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    severity: str = "info",
    user_id: Optional[str] = None,
    threshold_ratio: Optional[float] = None,
    dedupe_key: Optional[str] = None,
    defer_commit: bool = False,
) -> Optional[Notification]:
    """Create a notification if the org's rule allows it. Returns the row, or
    None when suppressed (rule disabled, threshold not crossed, or deduped)."""
    rule = get_rule(db, org_id, type)
    if not rule.get("enabled", True):
        return None

    # Threshold gating: only fire when the observed ratio crosses the configured
    # threshold (for "approaching"-style events).
    thr = rule.get("threshold")
    if thr is not None and threshold_ratio is not None and threshold_ratio < thr:
        return None

    # Dedupe: skip if a matching row was created recently.
    if dedupe_key:
        since = datetime.now(timezone.utc) - _DEDUPE_WINDOW
        existing = (
            db.query(Notification.id)
            .filter(
                Notification.organization_id == org_id,
                Notification.dedupe_key == dedupe_key,
                Notification.created_at >= since,
            )
            .first()
        )
        if existing:
            return None

    n = Notification(
        organization_id=org_id,
        user_id=user_id,
        type=type,
        severity=severity,
        title=title,
        body=body,
        link=link,
        dedupe_key=dedupe_key,
    )
    db.add(n)
    if not defer_commit:
        db.commit()
        db.refresh(n)

    # Email channel — best effort, non-blocking.
    if "email" in (rule.get("channels") or ""):
        _try_email(db, org_id, user_id, title, body or title)

    return n


def _try_email(db: Session, org_id: str, user_id: Optional[str], subject: str, html_body: str) -> None:
    """Fire an email to the target user (or org admins) without blocking. No-op
    if there's no running event loop or no resolvable recipient."""
    try:
        from app.services.email_service import send_email
        from app.models.identity import User, OrganizationMember

        recipients: list[str] = []
        if user_id:
            u = db.query(User).filter(User.id == user_id).first()
            if u and u.email:
                recipients.append(u.email)
        else:
            # org broadcast → email the org's admins (best effort, capped)
            members = (
                db.query(User.email)
                .join(OrganizationMember, OrganizationMember.user_id == User.id)
                .filter(OrganizationMember.organization_id == org_id)
                .limit(10)
                .all()
            )
            recipients = [e for (e,) in members if e]

        if not recipients:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.info("notification email skipped (no event loop) subject=%s", subject)
            return
        for to in recipients:
            loop.create_task(send_email(to=to, subject=subject, html_body=f"<p>{html_body}</p>"))
    except Exception:  # never let email break emit
        logger.exception("notification email failed")


# ----------------------------------- reads -----------------------------------

def list_notifications(db: Session, organization_id: str, user_id: str, *,
                       unread_only: bool = False, limit: int = 50, offset: int = 0) -> list[Notification]:
    q = (
        db.query(Notification)
        .filter(Notification.organization_id == organization_id)
        .filter(or_(Notification.user_id == user_id, Notification.user_id.is_(None)))
    )
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    return q.order_by(Notification.created_at.desc()).offset(offset).limit(min(limit, 200)).all()


def unread_count(db: Session, organization_id: str, user_id: str) -> int:
    return (
        db.query(Notification)
        .filter(Notification.organization_id == organization_id)
        .filter(or_(Notification.user_id == user_id, Notification.user_id.is_(None)))
        .filter(Notification.read_at.is_(None))
        .count()
    )


def mark_read(db: Session, organization_id: str, user_id: str, notification_id: str) -> bool:
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.organization_id == organization_id)
        .filter(or_(Notification.user_id == user_id, Notification.user_id.is_(None)))
        .first()
    )
    if not n:
        return False
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
    return True


def mark_all_read(db: Session, organization_id: str, user_id: str) -> int:
    rows = (
        db.query(Notification)
        .filter(Notification.organization_id == organization_id)
        .filter(or_(Notification.user_id == user_id, Notification.user_id.is_(None)))
        .filter(Notification.read_at.is_(None))
        .all()
    )
    now = datetime.now(timezone.utc)
    for n in rows:
        n.read_at = now
    if rows:
        db.commit()
    return len(rows)
