"""Knowledge-base endpoints — upload + keyword search.

MVP without vector embeddings. Keyword search uses ILIKE; switch to
tsvector + GIN index or pgvector when scale exceeds ~10k docs. The shape
of /knowledge/search stays stable across that swap.

BMAD agents call /knowledge/search?q={agent + project context} to enrich
their planning prompt with the operator's internal docs (Confluence dumps,
runbooks, schema dictionaries).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id, require_permission
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.models.knowledge import KnowledgeDoc

router = APIRouter(tags=["knowledge"])


class DocUpload(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source_url: str | None = Field(default=None, max_length=500)
    tags: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=200_000)


@router.post("/knowledge/docs", status_code=201)
def upload_doc(
    data: DocUpload,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    """Upload a knowledge-base document. Cap is 200 KB / doc to keep the
    table cheap; chunking pipeline is the caller's responsibility."""
    row = KnowledgeDoc(
        organization_id=org_id,
        title=data.title,
        source_url=data.source_url,
        tags=data.tags,
        content=data.content,
        content_length=len(data.content),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, org_id=org_id, actor_id=user_id, action="knowledge_doc_uploaded",
                entity_type="knowledge_doc", entity_id=row.id,
                meta={"title": data.title, "bytes": row.content_length},
                request=request)
    return _serialize(row, include_content=False)


@router.get("/knowledge/docs")
def list_docs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.organization_id == org_id)
        .order_by(KnowledgeDoc.created_at.desc())
        .offset(offset).limit(limit).all()
    )
    return [_serialize(r, include_content=False) for r in rows]


@router.get("/knowledge/docs/{doc_id}")
def get_doc(
    doc_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    row = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Doc not found")
    return _serialize(row, include_content=True)


@router.delete("/knowledge/docs/{doc_id}", status_code=204)
def delete_doc(
    doc_id: str,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    row = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Doc not found")
    db.delete(row)
    db.commit()
    write_audit(db, org_id=org_id, actor_id=user_id, action="knowledge_doc_deleted",
                entity_type="knowledge_doc", entity_id=doc_id, request=request)


@router.get("/knowledge/search")
def search_docs(
    q: str = Query(min_length=2, max_length=500),
    limit: int = Query(5, ge=1, le=20),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Top-N matching docs for a query. Returns the title + 400-char window
    around the first hit so agents can cite without bloating prompts."""
    needle = f"%{q}%"
    rows = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.organization_id == org_id)
        .filter(or_(
            KnowledgeDoc.title.ilike(needle),
            KnowledgeDoc.content.ilike(needle),
            KnowledgeDoc.tags.ilike(needle),
        ))
        .order_by(KnowledgeDoc.content_length.asc())  # short docs first — usually higher signal
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        excerpt = _excerpt(r.content, q, window=400)
        out.append({
            "id": r.id,
            "title": r.title,
            "source_url": r.source_url,
            "tags": r.tags,
            "excerpt": excerpt,
        })
    return out


# ── Helpers ────────────────────────────────────────────────────────────


def _serialize(row: KnowledgeDoc, *, include_content: bool) -> dict:
    out = {
        "id": row.id,
        "title": row.title,
        "source_url": row.source_url,
        "tags": row.tags,
        "content_length": row.content_length,
        "created_at": str(row.created_at) if row.created_at else None,
    }
    if include_content:
        out["content"] = row.content
    return out


def _excerpt(content: str, needle: str, *, window: int) -> str:
    idx = content.lower().find(needle.lower())
    if idx < 0:
        return content[:window]
    start = max(0, idx - window // 2)
    end = min(len(content), idx + window // 2)
    chunk = content[start:end]
    if start > 0:
        chunk = "…" + chunk
    if end < len(content):
        chunk = chunk + "…"
    return chunk
