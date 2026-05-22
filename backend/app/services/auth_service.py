import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.identity import User, Organization, OrganizationMember, Role, Permission
from app.auth.jwt import hash_password, verify_password, create_access_token
from app.schemas.identity import FirstAdminSetup


SYSTEM_PERMISSIONS = [
    "admin:users:read", "admin:users:write",
    "admin:roles:read", "admin:roles:write",
    "admin:llm:read", "admin:llm:write",
    "admin:audit:read",
    "project:read", "project:write",
    "agent:execute", "agent:approve",
    "artifact:upload", "artifact:review", "artifact:approve",
    "validation:execute", "reconciliation:execute",
    "report:export",
]

SYSTEM_ROLES = {
    "super_admin": ["*"],
    "admin": SYSTEM_PERMISSIONS,
    "project_manager": ["project:read", "project:write", "agent:approve", "report:export", "admin:audit:read"],
    "architect": ["project:read", "agent:execute"],
    "data_engineer": ["project:read", "agent:execute", "artifact:upload", "artifact:review", "validation:execute"],
    "qa_engineer": ["project:read", "validation:execute", "reconciliation:execute", "report:export"],
    "viewer": ["project:read", "admin:audit:read"],
}


def seed_permissions(db: Session):
    for code in SYSTEM_PERMISSIONS:
        if not db.query(Permission).filter(Permission.code == code).first():
            db.add(Permission(code=code, description=f"Permission: {code}"))
    db.commit()


def seed_roles(db: Session, organization_id: uuid.UUID):
    for role_name, perm_codes in SYSTEM_ROLES.items():
        existing = db.query(Role).filter(Role.organization_id == organization_id, Role.name == role_name).first()
        if not existing:
            role = Role(organization_id=organization_id, name=role_name, scope="organization", is_system=True)
            db.add(role)
            db.flush()
            if "*" in perm_codes:
                perms = db.query(Permission).all()
            else:
                perms = db.query(Permission).filter(Permission.code.in_(perm_codes)).all()
            role.permissions = perms
    db.commit()


def setup_first_admin(db: Session, data: FirstAdminSetup) -> dict:
    if db.query(User).filter(User.is_super_admin == True).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="First admin already exists")

    seed_permissions(db)

    org = Organization(name=data.organization_name, slug=data.organization_slug)
    db.add(org)
    db.flush()

    seed_roles(db, org.id)

    super_admin_role = db.query(Role).filter(Role.organization_id == org.id, Role.name == "super_admin").first()

    user = User(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        is_super_admin=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    membership = OrganizationMember(organization_id=org.id, user_id=user.id, role_id=super_admin_role.id)
    db.add(membership)
    db.commit()

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer", "user_id": str(user.id)}


def login(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account inactive")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


def get_current_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
