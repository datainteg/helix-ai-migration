"""Idempotent demo-organization bootstrap for "Login with Demo User".

Creates (once) a dedicated demo Organization (is_demo=True) + a read-only demo
User (the `viewer` role) + their membership. Demo sessions are scoped — like
any user — to this single org via get_current_organization_id, so demo users
only ever see the demo org's data and real orgs never see the demo's.

DB-only (no artifacts) so it is safe to call from the backend (which mounts the
artifact volume read-only). The demo migration CONTENT is seeded separately by
the worker CLI `app.cli.seed_demo_migration` targeting this org.
"""
from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth.jwt import hash_password
from app.models.identity import Organization, OrganizationMember, Role, User
from app.services.auth_service import seed_permissions, seed_roles

logger = logging.getLogger(__name__)

DEMO_ORG_SLUG = "helix-demo"
DEMO_ORG_NAME = "Helix Demo"
DEMO_USER_EMAIL = "demo@helix.local"
DEMO_USER_NAME = "Demo User"


def ensure_demo_org(db: Session) -> tuple[Organization, User]:
    """Get-or-create the demo org + demo user (read-only). Idempotent."""
    org = db.query(Organization).filter(Organization.slug == DEMO_ORG_SLUG).first()
    if org is None:
        seed_permissions(db)
        org = Organization(name=DEMO_ORG_NAME, slug=DEMO_ORG_SLUG, status="active", is_demo=True)
        db.add(org)
        db.flush()
        seed_roles(db, org.id)

    viewer = (
        db.query(Role)
        .filter(Role.organization_id == org.id, Role.name == "viewer")
        .first()
    )
    if viewer is None:
        # seed_roles should have created it; create a minimal read-only role if not.
        seed_roles(db, org.id)
        viewer = (
            db.query(Role)
            .filter(Role.organization_id == org.id, Role.name == "viewer")
            .first()
        )

    user = db.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    if user is None:
        user = User(
            email=DEMO_USER_EMAIL,
            name=DEMO_USER_NAME,
            # Random hash — demo-login never checks a password; this just
            # satisfies the NOT NULL column and blocks normal /auth/login.
            password_hash=hash_password(uuid4().hex),
            is_super_admin=False,
            status="active",
        )
        db.add(user)
        db.flush()

    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if member is None:
        db.add(
            OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role_id=viewer.id,
                status="active",
            )
        )

    db.commit()
    db.refresh(org)
    db.refresh(user)
    logger.info("Demo org ensured: org=%s user=%s", org.id, user.id)
    return org, user
