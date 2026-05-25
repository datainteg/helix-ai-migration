"""Knowledge-base document model for the BMAD RAG layer.

MVP stores plain-text + a tsvector for full-text search. A future vector
store (pgvector / Pinecone / Qdrant) plugs in without changing the API —
the search service is the seam.
"""

from sqlalchemy import Column, String, Text, Integer

from app.models.base import BaseModel


class KnowledgeDoc(BaseModel):
    __tablename__ = "knowledge_docs"

    organization_id = Column(String(36), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=True)
    tags = Column(String(500), nullable=True)  # comma-separated
    content = Column(Text, nullable=False)
    content_length = Column(Integer, default=0, nullable=False)
