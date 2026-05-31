"""Business sign-off requests (draft → send → approved/rejected).

Email is NOT auto-sent: a draft is created, the user reviews + sends via the
existing email settings. Attachments reference recon report / validation
summary / closure report files.
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON

from app.models.base import BaseModel


class SignoffRequest(BaseModel):
    __tablename__ = "signoff_requests"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    recon_report_id = Column(String(36), nullable=True)
    recipient_email = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    attachment_paths_json = Column(JSON, nullable=True)            # list[str]
    status = Column(String(20), default="draft", nullable=False, index=True)   # draft|sent|approved|rejected
    sent_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(String(36), nullable=True)
