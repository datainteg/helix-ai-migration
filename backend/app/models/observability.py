from sqlalchemy import Column, String, Text
from app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    organization_id = Column(String(36), nullable=False, index=True)
    actor_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(String(36), nullable=True)
    event_metadata = Column("metadata", Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)


class SystemHealthCheck(BaseModel):
    __tablename__ = "system_health_checks"
    component = Column(String(100), nullable=False)  # database, redis, temporal, worker, storage
    status = Column(String(50), nullable=False)  # healthy, degraded, down
    message = Column(String(500), nullable=True)
