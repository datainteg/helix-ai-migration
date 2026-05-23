from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.identity import UserLogin, TokenResponse, FirstAdminSetup, UserResponse
from app.services.auth_service import setup_first_admin, login, get_current_user
from app.auth.jwt import create_access_token, get_current_user_id, revoke_token
from app.api.audit import write_audit
from app.rate_limiting import limiter

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
