from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.identity import UserLogin, TokenResponse, FirstAdminSetup, UserResponse
from app.services.auth_service import setup_first_admin, login, get_current_user
from app.services.password_reset_service import request_password_reset, confirm_password_reset
from app.auth.jwt import create_access_token, get_current_user_id, revoke_token, register_sse_ticket
from app.api.audit import write_audit
from app.rate_limiting import limiter
from app.core.config import settings
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


@router.post("/auth/sse-ticket")
@limiter.limit("60/minute")
def issue_sse_ticket(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    user_id: str = Depends(get_current_user_id),
):
    """Mint a short-lived SSE-only token for use as a `?token=` URL param.

    Browser EventSource cannot set Authorization headers, so SSE endpoints must
    accept a token from the URL — but full-power access tokens in URLs leak
    into proxy/server logs and Referer headers. This endpoint trades a normal
    bearer token (sent in the request body via Authorization header) for a
    60-second token scoped to SSE only, narrowing the leak window.

    SEC-003: bind the ticket to the bearer that minted it — when the
    operator hits /auth/logout (or /auth/refresh), the ticket is revoked
    too, so a stolen SSE ticket cannot outlive its parent session.
    """
    from datetime import timedelta
    ttl_seconds = 60
    ticket = create_access_token(
        user_id,
        expires_delta=timedelta(seconds=ttl_seconds),
        extra_claims={"scope": "sse"},
    )
    register_sse_ticket(credentials.credentials, ticket, ttl_seconds)
    return {"ticket": ticket, "expires_in": ttl_seconds}


@router.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh_token(request: Request, credentials: HTTPAuthorizationCredentials = Depends(_bearer), user_id: str = Depends(get_current_user_id)):
    """Issue a fresh token. Revokes the old one."""
    revoke_token(credentials.credentials)
    new_token = create_access_token(user_id)
    return {"access_token": new_token, "token_type": "bearer"}


@router.post("/auth/password-reset/request", status_code=202)
@limiter.limit("5/minute")
async def request_reset(request: Request, data: PasswordResetRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Request a password reset token. Always returns 202 to avoid email enumeration."""
    raw_token = request_password_reset(db, data.email)
    if raw_token:
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        from app.services.email_service import send_email, render_password_reset_email
        subject, html = render_password_reset_email(reset_url)
        background_tasks.add_task(send_email, to=data.email, subject=subject, html_body=html)
    return {"status": "accepted", "message": "If that email exists, a reset link has been sent"}


@router.post("/auth/password-reset/confirm", status_code=200)
@limiter.limit("10/minute")
def confirm_reset(request: Request, data: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Apply a new password using a valid reset token."""
    confirm_password_reset(db, data.token, data.new_password)
    return {"status": "ok", "message": "Password updated successfully"}
