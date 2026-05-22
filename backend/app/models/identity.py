import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, func
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Organization(BaseModel):
    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(50), default="active", nullable=False)

    members = relationship("OrganizationMember", back_populates="organization")
    projects = relationship("Project", back_populates="organization")


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    status = Column(String(50), default="active", nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    memberships = relationship("OrganizationMember", back_populates="user")


class Role(BaseModel):
    __tablename__ = "roles"

    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(100), nullable=False)
    scope = Column(String(50), default="organization", nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)

    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")


class Permission(BaseModel):
    __tablename__ = "permissions"

    code = Column(String(100), unique=True, nullable=False)
    description = Column(String(500), nullable=True)

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


role_permissions = Table(
    "role_permissions",
    BaseModel.metadata,
    Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class OrganizationMember(BaseModel):
    __tablename__ = "organization_members"

    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False)
    status = Column(String(50), default="active", nullable=False)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")
