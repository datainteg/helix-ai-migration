"""User invitation flow: invite by email, accept link creates/joins account."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.identity import User, OrgInvitation, OrganizationMember, Role
from app.auth.jwt import hash_password, create_access_token

logger = logging.getLogger(__name__)

_INVITE_TTL_DAYS = 7


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_invitation(
    db: Session,
    org_id: str,
    inviter_user_id: str,
    email: str,
    role_name: str = "viewer",
) -> str:
    """Create invitation for email. Returns raw token."""
    existing_user = db.query(User).filter(User.email == email).first()
    existing_member = (
        db.query(OrganizationMember)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(User.email == email, OrganizationMember.organization_id == org_id)
        .first()
    )
    if existing_member:
        raise HTTPException(status_code=400, detail="User already member of this organization")

    pending = (
        db.query(OrgInvitation)
        .filter(
            OrgInvitation.organization_id == org_id,
            OrgInvitation.email == email,
            OrgInvitation.status == "pending",
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=409, detail="Invitation already pending for this email")

    role = db.query(Role).filter(Role.organization_id == org_id, Role.name == role_name).first()
    raw_token = secrets.token_urlsafe(32)
    invite = OrgInvitation(
        organization_id=org_id,
        invited_by_user_id=inviter_user_id,
        email=email,
        role_id=str(role.id) if role else None,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=_INVITE_TTL_DAYS),
    )
    db.add(invite)
    db.commit()
    logger.info("invitation_created org=%s email=%s", org_id, email)
    return raw_token


def accept_invitation(
    db: Session,
    raw_token: str,
    name: str,
    password: str,
) -> dict:
    """Accept invitation. Creates user if new, joins org, returns JWT."""
    token_hash = _hash_token(raw_token)
    invite = (
        db.query(OrgInvitation)
        .filter(
            OrgInvitation.token_hash == token_hash,
            OrgInvitation.status == "pending",
        )
        .first()
    )
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or already-used invitation")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invitation has expired")

    user = db.query(User).filter(User.email == invite.email).first()
    if not user:
        user = User(
            email=invite.email,
            name=name,
            password_hash=hash_password(password),
            status="active",
        )
        db.add(user)
        db.flush()

    default_role = (
        db.query(Role)
        .filter(Role.id == invite.role_id)
        .first()
        if invite.role_id
        else db.query(Role).filter(Role.organization_id == invite.organization_id, Role.name == "viewer").first()
    )

    membership = OrganizationMember(
        organization_id=invite.organization_id,
        user_id=str(user.id),
        role_id=str(default_role.id) if default_role else None,
    )
    db.add(membership)

    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("invitation_accepted user=%s org=%s", user.id, invite.organization_id)
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer"}


def list_invitations(db: Session, org_id: str) -> list[OrgInvitation]:
    return (
        db.query(OrgInvitation)
        .filter(OrgInvitation.organization_id == org_id)
        .order_by(OrgInvitation.created_at.desc())
        .all()
    )


def revoke_invitation(db: Session, org_id: str, invitation_id: str) -> None:
    invite = (
        db.query(OrgInvitation)
        .filter(OrgInvitation.id == invitation_id, OrgInvitation.organization_id == org_id)
        .first()
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invite.status = "revoked"
    db.commit()
