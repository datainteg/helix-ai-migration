"""Admin CLI for secret-key rotation.

Runnable as:
    python -m app.cli.rotate --help
    python -m app.cli.rotate rotate-keks --confirm
    python -m app.cli.rotate rotate-dek --org-id <ORG> --confirm
    python -m app.cli.rotate rotate-all-deks --confirm
    python -m app.cli.rotate rotate-all-deks --start-from <ORG> --confirm

All commands default to **dry-run** mode (no DB writes) unless
``--confirm`` is supplied. Exit code 0 on full success, 1 if any
per-row or per-org failure occurred (details logged to stderr).

Design notes
------------
- rotate-keks:
    Calls ``rotate_kek_secrets(db)`` which rewraps every flat-KEK
    ciphertext row (e.g. ``LLMProviderSecret.encrypted_api_key``) from
    the legacy sha256-derived key to the current direct Fernet key,
    then prints the counts. On ``--confirm`` the DB commit is
    permanent; in dry-run we execute the rewrap logic in a transaction
    and rollback to leave the DB untouched.

- rotate-dek:
    Calls ``rotate_dek(db, org_id)`` for the specified org. Re-encrypts
    every per-org DEK target column (empty by default — register new
    columns in ``_DEFAULT_PER_ORG_DEK_TARGETS``), then marks the old
    DEK inactive.

- rotate-all-deks:
    Iterates every organization in the DB and calls ``rotate_dek``
    per-org. ``--start-from <org_id>`` allows resuming a partial run.
    Progress is logged per-org; failed orgs are collected and reported
    in the exit summary without aborting remaining orgs.
"""

from __future__ import annotations

import sys
import logging
from typing import Optional

import click

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stderr,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_db():
    """Return a synchronous SQLAlchemy session (caller must close)."""
    from app.db.session import SessionLocal
    return SessionLocal()


def _all_org_ids(db, start_from: str | None = None) -> list[str]:
    """Return all organisation IDs, optionally skipping those before `start_from`."""
    from app.models.identity import Organization
    rows = db.query(Organization.id).order_by(Organization.id).all()
    ids = [r[0] for r in rows]
    if start_from:
        try:
            idx = ids.index(start_from)
            ids = ids[idx:]
        except ValueError:
            click.echo(
                f"[WARN] --start-from '{start_from}' not found in org list; "
                "starting from the beginning.",
                err=True,
            )
    return ids


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Helix secret-rotation admin commands.

    All commands run in DRY-RUN mode by default.  Add --confirm to
    commit changes to the database.
    """


# ── rotate-keks ───────────────────────────────────────────────────────────────

@cli.command("rotate-keks")
@click.option(
    "--confirm",
    is_flag=True,
    default=False,
    help="Actually commit the rewrapped ciphertext. Omit for a dry run.",
)
def rotate_keks(confirm: bool):
    """Rewrap all flat-KEK ciphertext from legacy sha256-derived key to direct key.

    Idempotent: rows already sealed with the direct key are skipped
    (rewrap_if_legacy returns None for them).

    Removes the need for the MultiFernet legacy-key fallback slot once
    all rows are rewrapped.
    """
    from app.services.envelope_encryption_service import rotate_kek_secrets

    if not confirm:
        click.echo(
            "[DRY-RUN] rotate-keks: would rewrap flat-KEK ciphertext rows.\n"
            "          Pass --confirm to commit.",
            err=False,
        )

    db = _get_db()
    try:
        if not confirm:
            # Execute inside a transaction and roll back so nothing is written.
            counts = rotate_kek_secrets(db)
            db.rollback()
            click.echo(f"[DRY-RUN] rows that WOULD be rewrapped: {counts}")
            click.echo("[DRY-RUN] No changes written (omit --confirm to keep dry-run).")
            sys.exit(0)

        counts = rotate_kek_secrets(db)
        total = sum(counts.values())
        click.echo(f"[OK] rotate-keks complete. Rows rewrapped: {counts}  (total={total})")
        click.echo(
            "[INFO] When all legacy rows are gone you may remove the\n"
            "       MultiFernet legacy-key slot from secret_service._get_fernet()."
        )
        sys.exit(0)
    except Exception as exc:
        logger.exception("rotate-keks failed: %s", exc)
        db.rollback()
        click.echo(f"[ERROR] rotate-keks failed: {exc}", err=True)
        sys.exit(1)
    finally:
        db.close()


# ── rotate-dek ────────────────────────────────────────────────────────────────

@cli.command("rotate-dek")
@click.option("--org-id", required=True, help="Organisation ID whose DEK to rotate.")
@click.option(
    "--confirm",
    is_flag=True,
    default=False,
    help="Actually commit the new DEK. Omit for a dry run.",
)
def rotate_dek_cmd(org_id: str, confirm: bool):
    """Rotate the per-org DEK for a single organisation.

    Steps (all atomic):
      1. Generate new DEK, KEK-wrap it, insert as active.
      2. Re-encrypt every per-org DEK ciphertext column (registered in
         _DEFAULT_PER_ORG_DEK_TARGETS) from old DEK to new DEK.
      3. Mark old DEK inactive + stamp rotated_at.
      4. Commit (or rollback on any failure).

    If no per-org DEK columns are registered the rewrapped dict will be
    empty — that is expected and not a bug. The DEK record rotation
    still happens so the new key version is in effect for future writes.
    """
    from app.services.envelope_encryption_service import rotate_dek

    if not confirm:
        click.echo(
            f"[DRY-RUN] rotate-dek: would rotate DEK for org '{org_id}'.\n"
            "          Pass --confirm to commit.",
            err=False,
        )

    db = _get_db()
    try:
        if not confirm:
            result = rotate_dek(db, org_id)
            db.rollback()
            click.echo(f"[DRY-RUN] rotation result (not committed): {result}")
            click.echo("[DRY-RUN] No changes written.")
            sys.exit(0)

        result = rotate_dek(db, org_id)
        click.echo(
            f"[OK] rotate-dek complete for org '{org_id}'. "
            f"new_version={result.get('new_version')}  "
            f"rewrapped={result.get('rewrapped')}"
        )
        sys.exit(0)
    except Exception as exc:
        logger.exception("rotate-dek failed for org=%s: %s", org_id, exc)
        db.rollback()
        click.echo(f"[ERROR] rotate-dek failed for org '{org_id}': {exc}", err=True)
        sys.exit(1)
    finally:
        db.close()


# ── rotate-all-deks ───────────────────────────────────────────────────────────

@cli.command("rotate-all-deks")
@click.option(
    "--confirm",
    is_flag=True,
    default=False,
    help="Actually commit each rotation. Omit for a dry run.",
)
@click.option(
    "--start-from",
    "start_from",
    default=None,
    help=(
        "Resume a partial run: skip all org IDs that sort before this value. "
        "The org with this ID IS included."
    ),
)
def rotate_all_deks(confirm: bool, start_from: Optional[str]):
    """Rotate per-org DEK for every organisation.

    Resumable via --start-from <org_id>. Per-org failures are collected
    and reported at the end; they do NOT abort remaining orgs.

    Exit code: 0 if all orgs rotated successfully; 1 if any failed.
    """
    from app.services.envelope_encryption_service import rotate_dek

    if not confirm:
        click.echo(
            "[DRY-RUN] rotate-all-deks: would rotate DEK for every org.\n"
            "          Pass --confirm to commit.",
            err=False,
        )

    db = _get_db()
    try:
        org_ids = _all_org_ids(db, start_from=start_from)
    except Exception as exc:
        logger.exception("rotate-all-deks: failed to list orgs: %s", exc)
        click.echo(f"[ERROR] could not list organisations: {exc}", err=True)
        db.close()
        sys.exit(1)

    total = len(org_ids)
    click.echo(
        f"[INFO] {'DRY-RUN ' if not confirm else ''}rotating DEKs for {total} org(s)"
        + (f" starting from '{start_from}'" if start_from else "")
    )

    failed: list[str] = []
    for idx, org_id in enumerate(org_ids, start=1):
        try:
            result = rotate_dek(db, org_id)
            if not confirm:
                db.rollback()
                click.echo(
                    f"  [{idx}/{total}] [DRY-RUN] org={org_id} "
                    f"new_version={result.get('new_version')} "
                    f"rewrapped={result.get('rewrapped')}"
                )
            else:
                click.echo(
                    f"  [{idx}/{total}] [OK] org={org_id} "
                    f"new_version={result.get('new_version')} "
                    f"rewrapped={result.get('rewrapped')}"
                )
        except Exception as exc:
            logger.exception("rotate-all-deks: org=%s failed: %s", org_id, exc)
            try:
                db.rollback()
            except Exception:
                pass
            failed.append(org_id)
            click.echo(f"  [{idx}/{total}] [FAIL] org={org_id}: {exc}", err=True)

    db.close()

    if not confirm:
        click.echo(
            f"\n[DRY-RUN] Summary: {total - len(failed)}/{total} orgs would rotate. "
            f"Failures: {len(failed)}. No changes written."
        )
    else:
        click.echo(
            f"\n[SUMMARY] {total - len(failed)}/{total} orgs rotated successfully."
        )
        if failed:
            click.echo(f"[SUMMARY] Failed orgs ({len(failed)}): {failed}", err=True)

    sys.exit(1 if failed else 0)


# ── entry-point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
