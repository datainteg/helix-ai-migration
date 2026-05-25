import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    status: str
    is_super_admin: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    preferences: Optional[dict] = None

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    """Partial update of user UI preferences. Keys are merged into existing prefs."""
    preferences: dict


class UserProfileUpdate(BaseModel):
    """Self-service update of the caller's name. Email change is intentionally
    not exposed here — email rotation is an admin-level operation."""
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrganizationCreate(BaseModel):
    name: str
    slug: str


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str
    scope: str = "organization"


class RoleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    scope: str
    is_system: bool

    model_config = {"from_attributes": True}


class FirstAdminSetup(BaseModel):
    email: EmailStr
    name: str
    password: str
    organization_name: str
    organization_slug: str
