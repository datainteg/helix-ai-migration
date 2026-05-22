from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.identity import UserLogin, TokenResponse, FirstAdminSetup, UserResponse
from app.services.auth_service import setup_first_admin, login, get_current_user
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit

router = APIRouter(tags=["auth"])


@router.post("/auth/first-admin", response_model=TokenResponse)
def create_first_admin(data: FirstAdminSetup, db: Session = Depends(get_db), request: Request = None):
    result = setup_first_admin(db, data)
    uid = result.get("user_id", "")
    user = get_current_user(db, uid)
    org_id = user.memberships[0].organization_id if user.memberships else ""
    write_audit(db, org_id, uid, "first_admin_created", "user", uid, request=request)
    return {"access_token": result["access_token"], "token_type": "bearer"}


@router.post("/auth/login", response_model=TokenResponse)
def user_login(data: UserLogin, db: Session = Depends(get_db)):
    return login(db, data.email, data.password)


@router.get("/auth/me", response_model=UserResponse)
def current_user(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return get_current_user(db, user_id)
