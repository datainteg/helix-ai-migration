"""Validation evidence + recon reports.

Metadata only — NO row-level production source/target data is stored. Evidence
is developer-uploaded test results; recon reports are the business-ready
reconciliation summaries (the existing `recon_runs`/`recon_results` stay for the
mechanical per-table counts).
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON

from app.models.base import BaseModel


class ValidationEvidence(BaseModel):
    __tablename__ = "validation_evidence"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    sprint_id = Column(String(36), nullable=True, index=True)
    artifact_id = Column(String(36), nullable=True)
    uploaded_by_user_id = Column(String(36), nullable=True)
    evidence_type = Column(String(60), nullable=False)              # test_result|screenshot|log|summary|json
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    content_json = Column(JSON, nullable=True)
    status = Column(String(30), default="uploaded", nullable=False, index=True)  # uploaded|under_review|accepted|rejected|changes_required
    reviewed_by_agent = Column(String(80), nullable=True)
    reviewed_by_user_id = Column(String(36), nullable=True)
    review_summary = Column(Text, nullable=True)


class ReconReport(BaseModel):
    __tablename__ = "recon_reports"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    sprint_id = Column(String(36), nullable=True, index=True)
    report_type = Column(String(60), default="business", nullable=False)   # business|technical|schema|row_count|checksum
    status = Column(String(30), default="draft", nullable=False, index=True)  # draft|generated|under_review|approved|rejected|changes_requested
    source_summary_json = Column(JSON, nullable=True)
    target_summary_json = Column(JSON, nullable=True)
    mismatch_summary_json = Column(JSON, nullable=True)
    business_rules_json = Column(JSON, nullable=True)
    report_markdown = Column(Text, nullable=True)
    report_pdf_path = Column(String(500), nullable=True)
    generated_by_agent = Column(String(80), nullable=True)
    approved_by_user_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
