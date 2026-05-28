from sqlalchemy import Column, String, Float, ForeignKey, Text, Integer, BigInteger, DateTime
from app.models.base import BaseModel


class ValidationRule(BaseModel):
    __tablename__ = "validation_rules"
    project_id = Column(String(36), nullable=False, index=True)
    rule_type = Column(String(50), nullable=False)
    target_ref = Column(String(255), nullable=True)
    definition = Column(Text, nullable=True)
    status = Column(String(50), default="active")


class ValidationRun(BaseModel):
    __tablename__ = "validation_runs"
    project_id = Column(String(36), nullable=False, index=True)
    started_by = Column(String(36), nullable=False)
    status = Column(String(50), default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class ValidationResult(BaseModel):
    __tablename__ = "validation_results"
    run_id = Column(String(36), ForeignKey("validation_runs.id"), nullable=False)
    rule_id = Column(String(36), ForeignKey("validation_rules.id"), nullable=False)
    status = Column(String(50), nullable=False)
    observed_value = Column(String(255), nullable=True)
    expected_value = Column(String(255), nullable=True)


class ReconRun(BaseModel):
    __tablename__ = "recon_runs"
    project_id = Column(String(36), nullable=False, index=True)
    source_ref = Column(String(255), nullable=True)
    target_ref = Column(String(255), nullable=True)
    status = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)


class ReconResult(BaseModel):
    __tablename__ = "recon_results"
    run_id = Column(String(36), ForeignKey("recon_runs.id"), nullable=False)
    result_type = Column(String(50), nullable=False)
    summary = Column(Text, nullable=True)
    # M-015: BigInteger — two large row counts (>= 2^31) overflow a plain
    # Integer column on insert. Row counts on real migrations routinely exceed
    # 2.1 billion, so the diff (`abs(source - target)`) must use 64-bit.
    mismatch_count = Column(BigInteger, nullable=True)
    details_ref = Column(String(500), nullable=True)
