"""Knowledge-base search backends.

Two backends live behind the same `search()` contract so the API doesn't
care which is active:

  - "keyword" — ILIKE over title/content/tags (current default).
  - "vector"  — pgvector cosine similarity once embeddings are populated.

Select via HELIX_KNOWLEDGE_BACKEND=keyword|vector. The vector backend
falls back to keyword automatically when pgvector is unavailable or the
docs lack embeddings — never a 500.

To populate embeddings:
  HELIX_KNOWLEDGE_BACKEND=vector
  HELIX_EMBED_PROVIDER=openai          # only one supported in MVP
  HELIX_EMBED_MODEL=text-embedding-3-small
  HELIX_EMBED_API_KEY=sk-...
  python -m backend.scripts.embed_knowledge

The seam is intentionally narrow — when an operator wants Pinecone /
Qdrant instead of pgvector, swap _vector_search() implementation.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeDoc

logger = logging.getLogger(__name__)


def _backend() -> str:
    return (os.getenv("HELIX_KNOWLEDGE_BACKEND") or "keyword").lower()


def search(db: Session, organization_id: str, q: str, *, limit: int = 5) -> list[dict]:
    """Backend-agnostic search. Falls back to keyword on any failure."""
    if _backend() == "vector":
        try:
            return _vector_search(db, organization_id, q, limit=limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector search failed, falling back to keyword: %s", exc)
    return _keyword_search(db, organization_id, q, limit=limit)


def _keyword_search(db: Session, organization_id: str, q: str, *, limit: int) -> list[dict]:
    needle = f"%{q}%"
    rows = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.organization_id == organization_id)
        .filter(or_(
            KnowledgeDoc.title.ilike(needle),
            KnowledgeDoc.content.ilike(needle),
            KnowledgeDoc.tags.ilike(needle),
        ))
        .order_by(KnowledgeDoc.content_length.asc())
        .limit(limit)
        .all()
    )
    return [_row_to_hit(r, q) for r in rows]


def _vector_search(db: Session, organization_id: str, q: str, *, limit: int) -> list[dict]:
    """pgvector cosine search. Requires:
      - pgvector extension on the DB (CREATE EXTENSION IF NOT EXISTS vector)
      - knowledge_docs.embedding column (alembic follow-up)
      - HELIX_EMBED_* env vars to compute the query embedding

    Not wired in this MVP — raises NotImplementedError so the caller falls
    back to keyword. Land alongside an alembic migration that adds the
    `embedding vector(1536)` column + an IVFFLAT index.
    """
    raise NotImplementedError("vector backend not yet wired — apply pgvector migration first")


def _row_to_hit(row: KnowledgeDoc, q: str) -> dict:
    excerpt = _excerpt(row.content, q, window=400)
    return {
        "id": row.id,
        "title": row.title,
        "source_url": row.source_url,
        "tags": row.tags,
        "excerpt": excerpt,
    }


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
