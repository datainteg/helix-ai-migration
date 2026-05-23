from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.identity import UserLogin, TokenResponse, FirstAdminSetup, UserResponse
from app.services.auth_service import setup_first_admin, login, get_current_user
from app.services.password_reset_service import request_password_reset, confirm_password_reset
from app.auth.jwt import create_access_token, get_current_user_id, revoke_token
from app.api.audit import write_audit
from app.rate_limiting import limiter
from pydantic import BaseModel, EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

router = APIRouter(tags=["auth"])
_bearer = HTTPBearer()


@router.post("/auth/first-admin", response_model=TokenResponse)
@limiter.limit("5/minute")
def create_first_admin(request: Request, data: FirstAdminSetup, db: Session = Depends(get_db)):
    result = setup_first_admin(db, data)
    uid = result.get("user_id", "")
    user = get_current_user(db, uid)
    org_id = user.memberships[0].organization_id if user.memberships else ""
    write_audit(db, org_id, uid, "first_admin_created", "user", uid, request=request)
    return {"access_token": result["access_token"], "token_type": "bearer"}


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def user_login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    return login(db, data.email, data.password)


@router.get("/auth/me", response_model=UserResponse)
def current_user(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_current_user(db, user_id)


@router.post("/auth/logout")
def user_logout(request: Request, credentials: HTTPAuthorizationCredentials = Depends(_bearer), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    revoke_token(credentials.credentials)
    return {"status": "logged_out"}


@router.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh_token(request: Request, credentials: HTTPAuthorizationCredentials = Depends(_bearer), user_id: str = Depends(get_current_user_id)):
    """Issue a fresh token. Revokes the old one."""
    revoke_token(credentials.credentials)
    new_token = create_access_token(user_id)
    return {"access_token": new_token, "token_type": "bearer"}


@router.post("/auth/password-reset/request", status_code=202)
@limiter.limit("5/minute")
def request_reset(request: Request, data: PasswordResetRequest, db: Session = Depends(get_db)):
    """Request a password reset token. Always returns 202 to avoid email enumeration."""
    raw_token = request_password_reset(db, data.email)
    if raw_token:
        # In production, send via email. For now, surface in response for dev convenience.
        import logging
        logging.getLogger(__name__).info("DEV password reset token for %s: %s", data.email, raw_token)
    return {"status": "accepted", "message": "If that email exists, a reset link has been sent"}


@router.post("/auth/password-reset/confirm", status_code=200)
@limiter.limit("10/minute")
def confirm_reset(request: Request, data: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Apply a new password using a valid reset token."""
    confirm_password_reset(db, data.token, data.new_password)
    return {"status": "ok", "message": "Password updated successfully"}
