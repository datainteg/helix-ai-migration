"""Source-schema snapshots for drift detection.

A `SourceSchemaSnapshot` captures every table + column in a source connection
at one point in time. Subsequent snapshots can be diffed against the original
to detect drift — columns added/dropped, types changed — so operators learn
about schema changes mid-migration before they break the workflow.
"""

from sqlalchemy import Column, String, DateTime, Text, Integer

from app.models.base import BaseModel


class SourceSchemaSnapshot(BaseModel):
    __tablename__ = "source_schema_snapshots"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    # FK is logical only — sources live in source_connections but a snapshot
    # also makes sense for an ad-hoc connector tested outside a saved row.
    source_ref = Column(String(255), nullable=False, index=True)
    # JSON blob: { "schemas": [...], "tables": [{schema,name,columns:[...]}] }.
    # Text + parse on read keeps the column dialect-agnostic.
    payload = Column(Text, nullable=False)
    table_count = Column(Integer, default=0, nullable=False)
    column_count = Column(Integer, default=0, nullable=False)
    taken_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text, nullable=True)
