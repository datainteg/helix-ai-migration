import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, BackgroundTasks, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.identity import User
from app.schemas.identity import UserLogin, TokenResponse, FirstAdminSetup, UserResponse
from app.services.auth_service import setup_first_admin, login, get_current_user
from app.services.password_reset_service import request_password_reset, confirm_password_reset
from app.auth.jwt import (
    create_access_token, get_current_user_id, revoke_token,
    register_sse_ticket, bind_sse_ticket, extract_token, AUTH_COOKIE_NAME,
)
from app.utils.client_ip import get_client_ip
from app.api.audit import write_audit
from app.rate_limiting import limiter
from app.core.config import settings
from app.security.password_policy import validate_password
from pydantic import BaseModel, EmailStr, field_validator

logger = logging.getLogger(__name__)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:  # SC-002
        return validate_password(v)


router = APIRouter(tags=["auth"])
# SC-010: optional bearer. The browser now authenticates via the HttpOnly
# `helix_token` cookie and sends NO Authorization header, so a required
# HTTPBearer() would 403 these endpoints before the cookie is ever read.
# `extract_token(request, credentials)` resolves header-then-cookie precedence.
_bearer = HTTPBearer(auto_error=False)


def _set_auth_cookie(response: Response, request: Request, token: str) -> None:
    """SC-010: issue the JWT as an HttpOnly cookie that JS cannot read.

    The token is STILL returned in the JSON body by every caller of this
    helper, so the Python/TS SDKs and CLI (which read `access_token` and send
    it as `Authorization: Bearer`) are completely unaffected. The cookie is
    purely additive — it exists so the browser frontend can stop persisting
    the token in `localStorage` (XSS-readable).

    - HttpOnly: JS / an injected XSS payload cannot exfiltrate it.
    - Secure: only sent over HTTPS in production OR whenever the current
      request is already HTTPS (covers https staging/preview behind Caddy,
      whose X-Forwarded-Proto is reflected into request.url.scheme).
    - SameSite=Strict: the browser never attaches the cookie to cross-site
      requests, which is the CSRF defence that motivated SC-035.
    - max_age matches the JWT's own expiry so the cookie self-evicts.
    """
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=(settings.APP_ENV == "production" or request.url.scheme == "https"),
        samesite="strict",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/auth/first-admin", response_model=TokenResponse)
@limiter.limit("5/minute")
def create_first_admin(request: Request, response: Response, data: FirstAdminSetup, db: Session = Depends(get_db)):
    # SC-011: require an out-of-band X-Setup-Token that matches the
    # operator-configured SETUP_TOKEN envvar. This closes the bootstrap race
    # where the first network caller after `alembic upgrade head` owns the
    # platform. If SETUP_TOKEN is not configured, the endpoint refuses
    # entirely — a noisy denial is safer than a TOFU bootstrap.
    expected = settings.SETUP_TOKEN
    if not expected:
        # Print to stderr / log once so the operator sees what to set.
        if not db.query(User).filter(User.is_super_admin == True).first():
            logger.critical(
                "POST /auth/first-admin invoked but SETUP_TOKEN is not "
                "configured. Set SETUP_TOKEN=<random hex> in the backend env "
                "and resend the request with header X-Setup-Token: <value>."
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="first-admin bootstrap is disabled: SETUP_TOKEN env var is not configured",
        )
    provided = request.headers.get("X-Setup-Token", "")
    # Constant-time comparison to avoid trivial timing oracle.
    import hmac as _hmac
    if not provided or not _hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid or missing X-Setup-Token",
        )

    result = setup_first_admin(db, data)
    uid = result.get("user_id", "")
    user = get_current_user(db, uid)
    org_id = user.memberships[0].organization_id if user.memberships else ""
    write_audit(db, org_id, uid, "first_admin_created", "user", uid, request=request)
    # SC-010: set the HttpOnly cookie AND keep returning the token in the body.
    _set_auth_cookie(response, request, result["access_token"])
    return {"access_token": result["access_token"], "token_type": "bearer"}


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def user_login(request: Request, response: Response, data: UserLogin, db: Session = Depends(get_db)):
    result = login(db, data.email, data.password)
    # SC-010: set the HttpOnly cookie AND keep returning the token in the body.
    _set_auth_cookie(response, request, result["access_token"])
    return result


@router.post("/auth/demo-login", response_model=TokenResponse)
@limiter.limit("10/minute")
def demo_login(request: Request, response: Response, db: Session = Depends(get_db)):
    """Log in as the read-only demo user (no password) for the seeded demo org.

    Gated by the ALLOW_DEMO_LOGIN env flag so production deploys can disable it.
    Mints the SAME HttpOnly cookie as a normal login; the session is scoped to
    the demo org by the usual org-membership resolution, so it can only see the
    demo data and real orgs never see it.
    """
    if not settings.ALLOW_DEMO_LOGIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo login is disabled")
    from app.services.demo_org import ensure_demo_org

    org, user = ensure_demo_org(db)
    # `is_demo` claim → the read-only-demo middleware (main.py) 403s any
    # mutating request carrying this token, so the shared demo data is safe.
    token = create_access_token(str(user.id), extra_claims={"is_demo": True})
    _set_auth_cookie(response, request, token)
    write_audit(db, org_id=org.id, actor_id=str(user.id), action="demo_login",
                entity_type="user", entity_id=str(user.id), request=request)
    return {"access_token": token, "token_type": "bearer", "user_id": str(user.id)}


@router.get("/auth/me", response_model=UserResponse)
def current_user(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_current_user(db, user_id)


@router.post("/auth/logout")
def user_logout(request: Request, response: Response, credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    # SC-010: revoke whichever token authenticated this request (header OR
    # cookie) and clear the HttpOnly cookie so the browser session is gone.
    revoke_token(extract_token(request, credentials))
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.post("/auth/sse-ticket")
@limiter.limit("60/minute")
def issue_sse_ticket(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
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

    SC-013: additionally bind the ticket to the caller's forwarded IP + a
    UA hash captured here. The SSE consume handlers verify both, so a ticket
    that leaks via a proxy access log / Referer header cannot be replayed
    from a different client even inside its 60s TTL. Now feasible because
    SC-051 gives a trustworthy client IP behind the proxy.
    """
    from datetime import timedelta
    ttl_seconds = 60
    # SC-010: resolve the minting bearer from header OR cookie. The SSE ticket
    # is bound to this parent token so logout/refresh cascades to it.
    parent_token = extract_token(request, credentials)
    ticket = create_access_token(
        user_id,
        expires_delta=timedelta(seconds=ttl_seconds),
        extra_claims={"scope": "sse"},
    )
    register_sse_ticket(parent_token, ticket, ttl_seconds)
    bind_sse_ticket(
        ticket,
        get_client_ip(request),
        request.headers.get("user-agent"),
        ttl_seconds,
    )
    return {"ticket": ticket, "expires_in": ttl_seconds}


@router.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh_token(request: Request, response: Response, credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), user_id: str = Depends(get_current_user_id)):
    """Issue a fresh token. Revokes the old one."""
    # SC-010: revoke whichever token (header OR cookie) authenticated this
    # request, mint a fresh one, refresh the HttpOnly cookie, and still return
    # the new token in the body for SDK/CLI callers.
    revoke_token(extract_token(request, credentials))
    new_token = create_access_token(user_id)
    _set_auth_cookie(response, request, new_token)
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
