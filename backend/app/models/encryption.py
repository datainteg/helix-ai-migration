from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, func
from app.models.base import BaseModel


class OrgDataEncryptionKey(BaseModel):
    """Per-org Data Encryption Key (DEK) stored envelope-encrypted with the master KEK.

    Uniqueness model (DI-C1 follow-up):
      The original schema marked `organization_id` as fully unique. That
      broke rotation: `rotate_dek` needs to keep the prior row in the
      table (flipped to `is_active=False`) so historical ciphertext can
      still be decrypted via `_get_dek_for_decrypt`. With a full unique
      index the second INSERT for the same org always fails with
      IntegrityError. We now enforce "at most one ACTIVE DEK per org"
      via a partial unique index — inactive historical rows are allowed
      to coexist. The partial index is created by migration
      `2af2b45b4051_dek_partial_unique_active.py`; we declare a matching
      Index here with `postgresql_where` so `Base.metadata.create_all`
      (used by tests) produces the same shape on Postgres.
    """
    __tablename__ = "org_data_encryption_keys"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_dek = Column(String(512), nullable=False)
    key_version = Column(String(50), default="1", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    rotated_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Partial unique: only ONE active DEK per org. Inactive historical
        # rows may coexist. On SQLite (tests) the partial WHERE is also
        # supported and behaves correctly.
        Index(
            "uq_org_dek_active_per_org",
            "organization_id",
            unique=True,
            postgresql_where=(is_active == True),  # noqa: E712
            sqlite_where=(is_active == True),  # noqa: E712
        ),
    )
