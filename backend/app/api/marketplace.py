"""Plugin marketplace catalog.

Static registry of community-contributed connectors + agent personas. Each
entry carries metadata + install instructions; actual plugin loading happens
at worker boot via the existing connectors/_marketplace/ + agents/_plugins/
directories (added when an operator installs a plugin).

This endpoint is browse-only; install is intentionally a manual step
(operators run `pip install …` or `helix plugins install …` to keep the
trust boundary explicit).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.jwt import get_current_user_id

router = APIRouter(tags=["marketplace"])


# Kind values are constrained to the union below so a typo
# (`?kind=Connecter`) returns 422 instead of silently `[]`. Defined here
# (before MarketplaceEntry) so the model field itself can use it — H-009.
MarketplaceKind = Literal["connector", "agent", "validator", "recipe"]


class MarketplaceEntry(BaseModel):
    id: str
    name: str
    # H-009: was `kind: str`, which accepted any string — a typo in the
    # hand-written CATALOG below (e.g. "recipes") would silently never
    # surface under a `?kind=recipe` filter. Pydantic now rejects the
    # whole catalog at import time if an entry's kind isn't in the union.
    kind: MarketplaceKind
    source_type: str | None = None
    target_type: str | None = None
    description: str
    license: str
    author: str
    homepage: str
    pip_package: str | None = None
    install_command: str
    risk: str  # "low" | "medium" | "high"


CATALOG: list[MarketplaceEntry] = [
    MarketplaceEntry(
        id="connector-mainframe-cobol",
        name="Mainframe COBOL Connector",
        kind="connector",
        source_type="cobol",
        target_type=None,
        description="Reads COBOL copybooks + flat-file EBCDIC sources. Translates packed-decimal + COMP-3 fields to UTF-8 JSON.",
        license="Apache-2.0",
        author="Helix Community",
        homepage="https://github.com/datainteg/helix-connectors/mainframe-cobol",
        pip_package="helix-connector-mainframe-cobol",
        install_command="pip install helix-connector-mainframe-cobol",
        risk="medium",
    ),
    MarketplaceEntry(
        id="connector-teradata",
        name="Teradata Connector",
        kind="connector",
        source_type="teradata",
        description="Teradata source connector via teradatasql. Handles PERIOD types + QUALIFY clauses.",
        license="Apache-2.0",
        author="Helix Community",
        homepage="https://github.com/datainteg/helix-connectors/teradata",
        pip_package="helix-connector-teradata",
        install_command="pip install helix-connector-teradata",
        risk="low",
    ),
    MarketplaceEntry(
        id="connector-vertica",
        name="Vertica Connector",
        kind="connector",
        source_type="vertica",
        description="Vertica source connector via vertica-python. Projects + flex-tables aware.",
        license="Apache-2.0",
        author="Helix Community",
        homepage="https://github.com/datainteg/helix-connectors/vertica",
        pip_package="helix-connector-vertica",
        install_command="pip install helix-connector-vertica",
        risk="low",
    ),
    MarketplaceEntry(
        id="agent-finops",
        name="FinOps Agent",
        kind="agent",
        description="Reviews migration scripts for cost drivers (large table scans, cross-zone egress, expensive UDF calls).",
        license="Apache-2.0",
        author="Helix Community",
        homepage="https://github.com/datainteg/helix-agents/finops",
        pip_package="helix-agent-finops",
        install_command="pip install helix-agent-finops",
        risk="low",
    ),
    MarketplaceEntry(
        id="agent-secops",
        name="SecOps Agent",
        kind="agent",
        description="Reviews artifacts for credential leaks, over-privileged grants, public bucket exposure.",
        license="Apache-2.0",
        author="Helix Community",
        homepage="https://github.com/datainteg/helix-agents/secops",
        pip_package="helix-agent-secops",
        install_command="pip install helix-agent-secops",
        risk="low",
    ),
    MarketplaceEntry(
        id="validator-pii-detector",
        name="PII Detector",
        kind="validator",
        description="Column-level Presidio scan over recon samples; flags PHI/PII before approval.",
        license="MIT",
        author="Helix Community",
        homepage="https://github.com/datainteg/helix-validators/pii-detector",
        pip_package="helix-validator-pii-detector",
        install_command="pip install helix-validator-pii-detector",
        risk="medium",
    ),
    MarketplaceEntry(
        id="recipe-soc2-pack",
        name="SOC 2 Validation Pack",
        kind="recipe",
        description="Pre-built validation rule pack: row counts, audit chain verify, encryption-at-rest checks, retention policy.",
        license="Apache-2.0",
        author="Helix Community",
        homepage="https://github.com/datainteg/helix-recipes/soc2",
        pip_package=None,
        install_command="helix recipes import soc2",
        risk="low",
    ),
]

_BY_ID = {e.id: e for e in CATALOG}


@router.get("/marketplace", response_model=list[MarketplaceEntry])
def list_marketplace(
    kind: MarketplaceKind | None = None,
    user_id: str = Depends(get_current_user_id),
):
    """List marketplace entries. Filter with `?kind=connector|agent|validator|recipe`."""
    rows = CATALOG if not kind else [e for e in CATALOG if e.kind == kind]
    return rows


@router.get("/marketplace/{entry_id}", response_model=MarketplaceEntry)
def get_marketplace_entry(entry_id: str, user_id: str = Depends(get_current_user_id)):
    entry = _BY_ID.get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Marketplace entry {entry_id!r} not found")
    return entry
