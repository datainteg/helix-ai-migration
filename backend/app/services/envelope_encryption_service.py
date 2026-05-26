"""Envelope encryption: per-org DEK encrypted with master KEK.

Flow:
  encrypt_for_org(org_id, plaintext)
    → fetch/create active DEK for org
    → decrypt DEK with KEK (master Fernet)
    → encrypt plaintext with DEK
    → return ciphertext

  decrypt_for_org(org_id, ciphertext)
    → fetch active DEK for org, try decrypt
    → on InvalidToken, walk historical (inactive) DEKs in reverse
      version order until one decrypts — supports reading data still
      sealed with a pre-rotation DEK before re-encryption finishes.

  rotate_dek(org_id)
    → generates new DEK
    → caller is REQUIRED to pass a list of (model, column) tuples so
      `re_encrypt_all_secrets` can decrypt-with-old/encrypt-with-new
      every ciphertext row before the old DEK is marked inactive.
    → only after re-encryption succeeds (or `force=True` with explicit
      acceptance) does the old DEK flip to is_active=False.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Iterable, Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.encryption import OrgDataEncryptionKey

logger = logging.getLogger(__name__)


def _kek_direct() -> Fernet:
    """Preferred: ENCRYPTION_KEY env var IS the Fernet key (no derivation)."""
    return Fernet(settings.ENCRYPTION_KEY.encode("utf-8"))


def _kek_legacy() -> Fernet:
    """Backward-compatible: sha256(ENCRYPTION_KEY) wrapped as Fernet.

    Matches the prior implementation. Kept ONLY to decrypt existing
    KEK-wrapped DEKs sealed before the fix.
    """
    raw = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def _kek() -> MultiFernet:
    """Encryption uses the direct key; decryption falls back to legacy."""
    return MultiFernet([_kek_direct(), _kek_legacy()])


def _get_active_dek_record(db: Session, org_id: str) -> OrgDataEncryptionKey | None:
    return (
        db.query(OrgDataEncryptionKey)
        .filter(
            OrgDataEncryptionKey.organization_id == org_id,
            OrgDataEncryptionKey.is_active == True,  # noqa: E712
        )
        .first()
    )


def _get_all_dek_records(db: Session, org_id: str) -> list[OrgDataEncryptionKey]:
    """Return every DEK (active + inactive) for an org, newest version first."""
    rows = (
        db.query(OrgDataEncryptionKey)
        .filter(OrgDataEncryptionKey.organization_id == org_id)
        .all()
    )
    # Sort by key_version DESC (newest first). Stored as String(50) but
    # treated as integer for ordering; non-numeric versions sort lexically last.
    def _ver(r: OrgDataEncryptionKey) -> int:
        try:
            return int(r.key_version)
        except (TypeError, ValueError):
            return -1
    return sorted(rows, key=_ver, reverse=True)


def _get_or_create_dek(db: Session, org_id: str) -> bytes:
    """Return plaintext DEK bytes for the ACTIVE record. Creates one if absent."""
    record = _get_active_dek_record(db, org_id)
    if record:
        return _kek().decrypt(record.encrypted_dek.encode())

    plaintext_dek = Fernet.generate_key()
    encrypted_dek = _kek().encrypt(plaintext_dek).decode()
    record = OrgDataEncryptionKey(
        organization_id=org_id,
        encrypted_dek=encrypted_dek,
    )
    db.add(record)
    db.commit()
    logger.info("org_dek_created org_id=%s", org_id)
    return plaintext_dek


def _get_dek_for_decrypt(db: Session, org_id: str, ciphertext: str) -> bytes:
    """Find a DEK that can decrypt the given ciphertext.

    Tries the active DEK first (fast path), then walks historical DEKs
    in reverse version order. Raises InvalidToken if none match.

    This is what makes rotation safe: during the (re-encrypt → flip
    is_active) transition, reads can still find data sealed with the
    old DEK.
    """
    candidates = _get_all_dek_records(db, org_id)
    if not candidates:
        raise InvalidToken("no DEK records for org")

    # Try active first
    active = [r for r in candidates if r.is_active]
    inactive = [r for r in candidates if not r.is_active]
    ordered = active + inactive

    kek = _kek()
    last_err: Exception | None = None
    ct_bytes = ciphertext.encode()
    for rec in ordered:
        try:
            dek = kek.decrypt(rec.encrypted_dek.encode())
            Fernet(dek).decrypt(ct_bytes)  # probe
            return dek
        except InvalidToken as exc:
            last_err = exc
            continue
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    raise InvalidToken(f"no DEK decrypted ciphertext for org={org_id}; last={last_err}")


def encrypt_for_org(db: Session, org_id: str, plaintext: str) -> str:
    """Encrypt plaintext with org-specific ACTIVE DEK."""
    dek = _get_or_create_dek(db, org_id)
    return Fernet(dek).encrypt(plaintext.encode()).decode()


def decrypt_for_org(db: Session, org_id: str, ciphertext: str) -> str:
    """Decrypt ciphertext using whichever org DEK can read it.

    Falls back through inactive DEKs so a half-rotated org still serves
    reads without data loss.
    """
    dek = _get_dek_for_decrypt(db, org_id, ciphertext)
    return Fernet(dek).decrypt(ciphertext.encode()).decode()


#: Default per-org DEK ciphertext columns to walk on `rotate_dek`.
#:
#: IMPORTANT (DI-C1 follow-up): this list MUST only contain columns
#: that were sealed with `encrypt_for_org` (per-org DEK), NOT with
#: `secret_service.encrypt_value` (flat-KEK MultiFernet). Mixing the
#: two causes `InvalidToken` on every row and rotation silently
#: rewraps nothing.
#:
#: As of 2026-05-26, NO production column uses `encrypt_for_org` yet —
#: `LLMProviderSecret.encrypted_api_key` is sealed via the flat-KEK
#: path (`secret_service.encrypt_value`) and must be rotated via the
#: KEK-rotation runbook in `docs/MIGRATION_NOTES.md`, not via this
#: function. When a new column starts using the per-org DEK, register
#: it here.
_DEFAULT_PER_ORG_DEK_TARGETS: list[tuple[type, str]] = []


def re_encrypt_all_secrets(
    db: Session,
    org_id: str,
    old_dek: bytes,
    new_dek: bytes,
    *,
    targets: Sequence[tuple[type, str]] | None = None,
) -> dict[str, int]:
    """Decrypt-with-old/encrypt-with-new for every per-org DEK column.

    `targets` is an explicit list of (Model, column_name) pairs the
    caller knows are encrypted with the **per-org DEK** (i.e. via
    `encrypt_for_org`). Auto-discovery is intentionally avoided so a
    forgotten registration is caught in code review rather than at
    rotation time.

    Default targets: empty. The flat-KEK column
    `LLMProviderSecret.encrypted_api_key` is NOT included — it is
    sealed via `secret_service.encrypt_value` (MultiFernet over the
    master KEK), so passing it here would raise `InvalidToken` on
    every row and silently rewrap nothing. Rotate that column via the
    KEK runbook (see `docs/MIGRATION_NOTES.md`).

    Returns: {table_name: rows_rewrapped}
    """
    effective_targets: Sequence[tuple[type, str]] = (
        list(_DEFAULT_PER_ORG_DEK_TARGETS) if targets is None else targets
    )

    old_f = Fernet(old_dek)
    new_f = Fernet(new_dek)
    counts: dict[str, int] = {}

    for Model, col in effective_targets:
        if hasattr(Model, "organization_id"):
            rows = db.query(Model).filter(Model.organization_id == org_id).all()
        else:
            logger.warning(
                "re_encrypt_all_secrets: no organization_id on %s; "
                "register a join path before adding to targets. Skipping.",
                Model.__name__,
            )
            continue

        rewrapped = 0
        for row in rows:
            ct = getattr(row, col, None)
            if not ct:
                continue
            try:
                pt = old_f.decrypt(ct.encode())
            except InvalidToken:
                # Already encrypted with new DEK (idempotent re-run)
                # or registered in error against a column NOT sealed
                # with the per-org DEK. Skip — caller must handle
                # the flat-KEK path separately via rotate_kek_secrets.
                continue
            setattr(row, col, new_f.encrypt(pt).decode())
            rewrapped += 1

        counts[Model.__tablename__] = rewrapped

    db.flush()
    return counts


def rotate_kek_secrets(db: Session) -> dict[str, int]:
    """Rewrap every flat-KEK ciphertext column from the legacy KEK to the direct KEK.

    Walks the columns that are sealed with `secret_service.encrypt_value`
    (MultiFernet over the master KEK) and opportunistically rewraps any
    row whose ciphertext is still using the legacy sha256-derived key.

    Separate from `re_encrypt_all_secrets` (the per-org DEK rotator)
    because:
      - The KEK is global, not per-org.
      - Rotation here is "promote legacy ciphertext to the direct key"
        rather than "re-key with a brand-new key".
      - Mixing the two paths produces silent `InvalidToken` skips and
        is the bug DI-C1 was reopened for.

    Returns: {table_name: rows_rewrapped}
    """
    from app.models.llm import LLMProviderSecret
    from app.services.secret_service import rewrap_if_legacy

    # (Model, column_name) — every column sealed via flat-KEK encrypt_value.
    flat_kek_targets: list[tuple[type, str]] = [
        (LLMProviderSecret, "encrypted_api_key"),
    ]

    counts: dict[str, int] = {}
    for Model, col in flat_kek_targets:
        rows = db.query(Model).all()
        rewrapped = 0
        for row in rows:
            ct = getattr(row, col, None)
            new_ct = rewrap_if_legacy(ct)
            if new_ct is None:
                continue
            setattr(row, col, new_ct)
            rewrapped += 1
        counts[Model.__tablename__] = rewrapped

    db.commit()
    logger.info("kek_secrets_rewrapped counts=%s", counts)
    return counts


def rotate_dek(
    db: Session,
    org_id: str,
    *,
    targets: Sequence[tuple[type, str]] | None = None,
    force: bool = False,
) -> dict:
    """Rotate the org DEK SAFELY.

    Steps (all in one transaction):
      1. Load old active DEK plaintext.
      2. Generate new DEK + KEK-wrap + insert with is_active=True.
      3. Re-encrypt every per-org ciphertext column from old→new.
      4. Mark old DEK is_active=False, rotated_at=now.
      5. Commit.

    If step 3 raises and `force=False`, the whole transaction rolls back
    so the old DEK remains the active one and no data is bricked. With
    `force=True` the new DEK is committed regardless (DESTRUCTIVE — only
    use in disaster-recovery flows where the old key is unrecoverable).
    """
    old = _get_active_dek_record(db, org_id)

    if old is None:
        # First rotation == first DEK creation — no re-encryption needed.
        plaintext_dek = Fernet.generate_key()
        new_record = OrgDataEncryptionKey(
            organization_id=org_id,
            encrypted_dek=_kek().encrypt(plaintext_dek).decode(),
            key_version="1",
        )
        db.add(new_record)
        db.commit()
        logger.info("org_dek_initial_create org_id=%s", org_id)
        return {"created": True, "rewrapped": {}}

    try:
        old_plain = _kek().decrypt(old.encrypted_dek.encode())
    except InvalidToken as exc:
        # Old DEK can't be unwrapped (KEK rotated externally?). Without
        # the old plaintext we cannot re-encrypt anything. Abort unless
        # operator confirms force.
        if not force:
            raise RuntimeError(
                f"rotate_dek: old DEK unwrap failed for org={org_id} ({exc}); "
                "refusing to rotate without --force (would orphan ciphertext)"
            )
        old_plain = None

    new_plain = Fernet.generate_key()
    new_version = str(int(old.key_version) + 1) if old.key_version and old.key_version.isdigit() else "2"

    new_record = OrgDataEncryptionKey(
        organization_id=org_id,
        encrypted_dek=_kek().encrypt(new_plain).decode(),
        key_version=new_version,
        is_active=True,
    )
    # Partial unique index `uq_org_dek_active_per_org` (migration
    # 2af2b45b4051) permits unlimited historical rows per org but only
    # one active row. We flip the old row to inactive BEFORE inserting
    # the new active one and flush both together so the unique-active
    # invariant holds at commit. On failure, rollback restores both.
    old.is_active = False
    old.rotated_at = datetime.now(timezone.utc)
    db.add(new_record)
    db.flush()  # apply the active-flip + new insert atomically within the txn

    try:
        if old_plain is None:
            counts: dict[str, int] = {}
        else:
            counts = re_encrypt_all_secrets(
                db, org_id, old_plain, new_plain, targets=targets
            )
    except Exception:
        db.rollback()
        raise

    db.commit()
    logger.info(
        "org_dek_rotated org_id=%s new_version=%s rewrapped=%s",
        org_id, new_version, counts,
    )
    return {"created": False, "rewrapped": counts, "new_version": new_version}
