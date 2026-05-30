"""Email / SMTP settings model.

One row per organization. Holds the admin-configured mail transport so SMTP
can be set up + tested from the UI without editing .env or restarting. The
SMTP password and SendGrid API key are stored encrypted (secret_service).

When a row exists and is enabled, email_service prefers it over the env-based
settings; otherwise it falls back to the .env config.
"""

from sqlalchemy import Column, String, Integer, Boolean

from app.models.base import BaseModel


class EmailSettings(BaseModel):
    __tablename__ = "email_settings"

    organization_id = Column(String(36), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, default=False, nullable=False)
    # "smtp" | "sendgrid"
    provider = Column(String(20), default="smtp", nullable=False)

    # Common
    from_email = Column(String(255), nullable=True)
    from_name = Column(String(255), nullable=True)

    # SMTP
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_user = Column(String(255), nullable=True)
    smtp_password_enc = Column(String(1000), nullable=True)  # encrypted at rest
    smtp_tls = Column(Boolean, default=True, nullable=False)

    # SendGrid
    sendgrid_api_key_enc = Column(String(1000), nullable=True)  # encrypted at rest
