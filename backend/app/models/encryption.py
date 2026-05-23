from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from app.models.base import BaseModel


class OrgDataEncryptionKey(BaseModel):
    """Per-org Data Encryption Key (DEK) stored envelope-encrypted with the master KEK."""
    __tablename__ = "org_data_encryption_keys"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    encrypted_dek = Column(String(512), nullable=False)
    key_version = Column(String(50), default="1", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    rotated_at = Column(DateTime(timezone=True), nullable=True)
