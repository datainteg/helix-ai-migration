"""Tests for the rotate CLI orchestrator (wave-3).

Coverage:
  T1  rotate-keks dry-run  — no DB modifications
  T2  rotate-keks --confirm — all 5 legacy-sealed rows decryptable with
                              direct key afterward, none with legacy-only key
  T3  rotate-dek dry-run   — no DEK record changes
  T4  rotate-dek --confirm — old DEK marked inactive; new ciphertext decrypts
  T5  rotate-all-deks --confirm over 3 orgs — all 3 rotated; old DEKs inactive
  T6  rotate-all-deks dry-run — no DB changes

These tests exercise the CLI commands via Click's CliRunner so they
capture stdout/exit-codes without spawning a subprocess, while still
running against the real SQLite in-process DB (same pattern as the
existing test suite).
"""

from __future__ import annotations

import base64
import hashlib
import uuid

import pytest
from click.testing import CliRunner
from cryptography.fernet import Fernet, InvalidToken

from app.cli.rotate import cli
from app.models.encryption import OrgDataEncryptionKey
from app.models.identity import Organization
from app.models.llm import LLMProvider, LLMProviderSecret
from app.services.secret_service import decrypt_value, encrypt_value


# ── test helpers ──────────────────────────────────────────────────────────────

def _make_org(db) -> str:
    org_id = str(uuid.uuid4())
    db.add(Organization(id=org_id, name="t", slug=f"t-{uuid.uuid4().hex[:8]}"))
    db.commit()
    return org_id


def _make_provider(db, org_id: str) -> str:
    prov_id = str(uuid.uuid4())
    db.add(LLMProvider(
        id=prov_id,
        organization_id=org_id,
        provider_type="openai",
        name="test",
        default_model="gpt-4",
    ))
    db.commit()
    return prov_id


def _legacy_fernet() -> Fernet:
    """Reproduce the old sha256-derived key used before wave-1."""
    from app.core.config import settings
    raw = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def _direct_fernet() -> Fernet:
    from app.core.config import settings
    return Fernet(settings.ENCRYPTION_KEY.encode("utf-8"))


def _seal_with_legacy(plaintext: str) -> str:
    """Seal with the old sha256-derived key so rotate-keks has something to rewrap."""
    return _legacy_fernet().encrypt(plaintext.encode()).decode()


def _invoke(args: list[str], db_session) -> "Result":  # noqa: F821
    """Run a CLI command with the db_session patched into SessionLocal."""
    from unittest.mock import patch, MagicMock

    # The CLI calls _get_db() which does SessionLocal(). We patch SessionLocal
    # to return the test db_session so all commands run against the test DB.
    session_mock = MagicMock()
    session_mock.return_value = db_session

    runner = CliRunner(mix_stderr=False)
    with patch("app.cli.rotate._get_db", return_value=db_session):
        result = runner.invoke(cli, args, catch_exceptions=False)
    return result


# ── T1: rotate-keks dry-run ──────────────────────────────────────────────────

def test_rotate_keks_dry_run_does_not_modify_db(db_session):
    """Dry-run must not commit any changes."""
    org_id = _make_org(db_session)
    prov_id = _make_provider(db_session, org_id)

    # Seal 5 secrets with the legacy key
    secret_ids = []
    for i in range(5):
        s = LLMProviderSecret(
            id=str(uuid.uuid4()),
            provider_id=prov_id,
            encrypted_api_key=_seal_with_legacy(f"sk-legacy-{i}"),
            key_version=1,
        )
        db_session.add(s)
        secret_ids.append(s.id)
    db_session.commit()

    # Capture the original ciphertext values before invocation
    before = {
        s.id: s.encrypted_api_key
        for s in db_session.query(LLMProviderSecret)
        .filter(LLMProviderSecret.provider_id == prov_id)
        .all()
    }

    result = _invoke(["rotate-keks"], db_session)
    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output

    # Refresh DB state — values must be identical (no commit happened)
    db_session.expire_all()
    after = {
        s.id: s.encrypted_api_key
        for s in db_session.query(LLMProviderSecret)
        .filter(LLMProviderSecret.provider_id == prov_id)
        .all()
    }
    assert before == after, "Dry-run must not modify any rows"


# ── T2: rotate-keks --confirm ─────────────────────────────────────────────────

def test_rotate_keks_confirm_rewraps_to_direct_key(db_session):
    """After --confirm all 5 rows decrypt with the direct key; legacy alone fails."""
    org_id = _make_org(db_session)
    prov_id = _make_provider(db_session, org_id)

    plaintexts = [f"sk-legacy-secret-{i}" for i in range(5)]
    for pt in plaintexts:
        db_session.add(LLMProviderSecret(
            id=str(uuid.uuid4()),
            provider_id=prov_id,
            encrypted_api_key=_seal_with_legacy(pt),
            key_version=1,
        ))
    db_session.commit()

    result = _invoke(["rotate-keks", "--confirm"], db_session)
    assert result.exit_code == 0, result.output
    assert "[OK]" in result.output

    db_session.expire_all()
    direct = _direct_fernet()
    legacy = _legacy_fernet()

    rows = (
        db_session.query(LLMProviderSecret)
        .filter(LLMProviderSecret.provider_id == prov_id)
        .all()
    )
    assert len(rows) == 5

    for row in rows:
        ct = row.encrypted_api_key.encode()
        # Must decrypt with the direct key
        pt = direct.decrypt(ct).decode()
        assert pt.startswith("sk-legacy-secret-"), f"Expected legacy plaintext, got {pt!r}"

        # Must NOT be readable by the legacy-only key
        with pytest.raises(InvalidToken):
            legacy.decrypt(ct)


# ── T3: rotate-dek dry-run ────────────────────────────────────────────────────

def test_rotate_dek_dry_run_does_not_modify_db(db_session):
    """Dry-run rotate-dek must not change DEK records."""
    from app.services.envelope_encryption_service import encrypt_for_org

    org_id = _make_org(db_session)
    encrypt_for_org(db_session, org_id, "canary-value")

    before_count = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id)
        .count()
    )
    before_active = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id, is_active=True)
        .first()
    )
    before_version = before_active.key_version

    result = _invoke(["rotate-dek", "--org-id", org_id], db_session)
    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output

    db_session.expire_all()
    after_count = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id)
        .count()
    )
    after_active = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id, is_active=True)
        .first()
    )

    assert after_count == before_count, "Dry-run must not insert new DEK records"
    assert after_active.key_version == before_version, "Dry-run must not change active key version"
    assert after_active.is_active is True


# ── T4: rotate-dek --confirm ─────────────────────────────────────────────────

def test_rotate_dek_confirm_marks_old_inactive_and_new_ciphertext_decrypts(db_session):
    """After rotation: old DEK inactive, new ciphertext decryptable."""
    from app.services.envelope_encryption_service import (
        decrypt_for_org,
        encrypt_for_org,
    )

    org_id = _make_org(db_session)
    plaintext = "rotate-dek-canary-abc123"
    old_ct = encrypt_for_org(db_session, org_id, plaintext)

    old_record = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id, is_active=True)
        .first()
    )
    old_version = old_record.key_version

    result = _invoke(["rotate-dek", "--org-id", org_id, "--confirm"], db_session)
    assert result.exit_code == 0, result.output
    assert "[OK]" in result.output

    db_session.expire_all()

    # Old record must now be inactive with rotated_at set
    old = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id, key_version=old_version)
        .first()
    )
    assert old is not None
    assert old.is_active is False
    assert old.rotated_at is not None

    # New active record must exist with bumped version
    new_active = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_id, is_active=True)
        .first()
    )
    assert new_active is not None
    assert new_active.key_version != old_version

    # Old ciphertext sealed with old DEK must still decrypt (historical DEK walk)
    recovered = decrypt_for_org(db_session, org_id, old_ct)
    assert recovered == plaintext

    # New writes use the new DEK and also decrypt correctly
    new_ct = encrypt_for_org(db_session, org_id, "post-rotation-value")
    assert decrypt_for_org(db_session, org_id, new_ct) == "post-rotation-value"


# ── T5: rotate-all-deks --confirm ─────────────────────────────────────────────

def test_rotate_all_deks_confirm_rotates_all_three_orgs(db_session):
    """All 3 orgs must have their DEKs rotated; old DEKs inactive."""
    from app.services.envelope_encryption_service import encrypt_for_org

    org_ids = [_make_org(db_session) for _ in range(3)]
    for oid in org_ids:
        encrypt_for_org(db_session, oid, f"secret-for-{oid}")

    result = _invoke(["rotate-all-deks", "--confirm"], db_session)
    assert result.exit_code == 0, result.output
    assert "[SUMMARY]" in result.output

    db_session.expire_all()
    for oid in org_ids:
        deks = (
            db_session.query(OrgDataEncryptionKey)
            .filter_by(organization_id=oid)
            .all()
        )
        active = [d for d in deks if d.is_active]
        inactive = [d for d in deks if not d.is_active]
        assert len(active) == 1, f"org {oid} should have exactly 1 active DEK"
        assert len(inactive) >= 1, f"org {oid} should have at least 1 inactive (old) DEK"
        assert all(d.rotated_at is not None for d in inactive), (
            f"org {oid}: rotated_at must be set on inactive DEKs"
        )


# ── T6: rotate-all-deks dry-run ───────────────────────────────────────────────

def test_rotate_all_deks_dry_run_no_changes(db_session):
    """Dry-run rotate-all-deks must not modify any DEK records."""
    from app.services.envelope_encryption_service import encrypt_for_org

    org_ids = [_make_org(db_session) for _ in range(3)]
    for oid in org_ids:
        encrypt_for_org(db_session, oid, f"secret-{oid}")

    # Snapshot state before
    before: dict[str, dict] = {}
    for oid in org_ids:
        rec = (
            db_session.query(OrgDataEncryptionKey)
            .filter_by(organization_id=oid, is_active=True)
            .first()
        )
        before[oid] = {"version": rec.key_version, "dek": rec.encrypted_dek}

    result = _invoke(["rotate-all-deks"], db_session)
    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output

    db_session.expire_all()
    for oid in org_ids:
        count = (
            db_session.query(OrgDataEncryptionKey)
            .filter_by(organization_id=oid)
            .count()
        )
        assert count == 1, f"Dry-run must not insert new DEK records for org {oid}"
        rec = (
            db_session.query(OrgDataEncryptionKey)
            .filter_by(organization_id=oid, is_active=True)
            .first()
        )
        assert rec.key_version == before[oid]["version"], (
            f"Dry-run must not change key version for org {oid}"
        )
        assert rec.encrypted_dek == before[oid]["dek"], (
            f"Dry-run must not change encrypted_dek for org {oid}"
        )


# ── T7: rotate-all-deks --start-from resumes from correct org ─────────────────

def test_rotate_all_deks_start_from_skips_earlier_orgs(db_session):
    """--start-from must skip orgs that sort before the given ID."""
    from app.services.envelope_encryption_service import encrypt_for_org

    # Create 3 orgs with deterministic IDs that sort predictably
    org_ids = sorted([_make_org(db_session) for _ in range(3)])
    for oid in org_ids:
        encrypt_for_org(db_session, oid, f"secret-{oid}")

    start_org = org_ids[1]  # skip org_ids[0], rotate org_ids[1] and org_ids[2]

    result = _invoke(["rotate-all-deks", "--start-from", start_org, "--confirm"], db_session)
    assert result.exit_code == 0, result.output

    db_session.expire_all()

    # org_ids[0] should NOT have been rotated (still only 1 DEK record)
    count_skipped = (
        db_session.query(OrgDataEncryptionKey)
        .filter_by(organization_id=org_ids[0])
        .count()
    )
    assert count_skipped == 1, "Org before start-from should not have been rotated"

    # org_ids[1] and org_ids[2] SHOULD have been rotated (2 records each)
    for oid in org_ids[1:]:
        count = (
            db_session.query(OrgDataEncryptionKey)
            .filter_by(organization_id=oid)
            .count()
        )
        assert count == 2, f"Org {oid} (at/after start-from) should have been rotated"
