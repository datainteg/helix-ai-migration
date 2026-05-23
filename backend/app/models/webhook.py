from sqlalchemy import Column, String, Boolean, Text
from app.models.base import BaseModel


class WebhookEndpoint(BaseModel):
    __tablename__ = "webhook_endpoints"

    organization_id = Column(String(36), nullable=False, index=True)
    url = Column(Text, nullable=False)
    secret = Column(String(255), nullable=True)
    events = Column(Text, nullable=False, default="*")  # comma-separated or "*"
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(String(255), nullable=True)


class WebhookDelivery(BaseModel):
    __tablename__ = "webhook_deliveries"

    endpoint_id = Column(String(36), nullable=False, index=True)
    event = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False)
    status_code = Column(String(10), nullable=True)
    response_body = Column(Text, nullable=True)
    success = Column(Boolean, nullable=True)
    error = Column(Text, nullable=True)
