"""Notification models.

Two tables:
  notifications        one row per in-app notification (per-user or org broadcast)
  notification_rules   per-org config: which events fire, thresholds, channels

Notifications are emitted by `notification_service.emit` from the cost
enforcement path (cap approaching / breached) and workflow failures. The
frontend bell polls the unread count; an SSE stream is available for live push.
"""

from sqlalchemy import Column, String, Text, Boolean, Float, DateTime, Index, UniqueConstraint

from app.models.base import BaseModel


class Notification(BaseModel):
    """One in-app notification. `user_id` NULL = org-wide broadcast (shown to
    every member of the org)."""

    __tablename__ = "notifications"

    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)  # NULL = org broadcast
    type = Column(String(60), nullable=False)                # cost.cap_breached | workflow.failed | ...
    severity = Column(String(20), default="info", nullable=False)  # info|warning|error|success
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String(500), nullable=True)                # in-app route, e.g. /admin/cost-limits
    # Dedupe guard so repeating emits (e.g. "cap breached" every workflow start)
    # don't spam — emit() skips when a recent row shares this key.
    dedupe_key = Column(String(120), nullable=True, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_notifications_org_user_read", "organization_id", "user_id", "read_at"),
        Index("ix_notifications_org_created", "organization_id", "created_at"),
    )


class NotificationRule(BaseModel):
    """Per-org rule controlling whether an event type fires, at what threshold,
    and through which channels. One row per (org, event_type)."""

    __tablename__ = "notification_rules"

    organization_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(60), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    # For threshold-based events (e.g. cost cap), the ratio at which to fire
    # the "approaching" notification (0.8 = 80%). NULL for non-threshold events.
    threshold = Column(Float, nullable=True)
    # CSV of delivery channels: "in_app" and/or "email".
    channels = Column(String(255), default="in_app", nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "event_type", name="uq_notif_rule_org_event"),
    )
