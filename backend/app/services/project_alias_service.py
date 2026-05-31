"""Project alias (HXM-NNNNNN) helpers — the public, business-facing id used in
headings, reports, emails and artifacts. The internal UUID + the URL slug stay
as-is; alias is purely the human/business identifier.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.project_service import generate_unique_alias


def ensure_alias(db: Session, project) -> str:
    """Return the project's alias, generating + persisting one if missing
    (e.g. for legacy rows that predate the column)."""
    alias = getattr(project, "alias", None)
    if not alias:
        alias = generate_unique_alias(db)
        project.alias = alias
        db.commit()
    return alias


def sprint_alias(project_alias: str, sprint_index: int) -> str:
    """Derive a sprint alias from the project alias, e.g. HXM-482913-S1."""
    return f"{project_alias}-S{sprint_index}"
