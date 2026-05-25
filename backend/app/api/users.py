"""User-scoped endpoints — preferences sync.

Holds per-user UI tweaks (theme, density, font size, surface tint, primary
color, notification toggles) so frontends across browsers/devices stay in
sync. PATCH merges (does not replace) so a partial save from one device
doesn't blow away other fields. GET returns the current dict.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth.jwt import get_current_user_id
from app.db.session import get_db
from app.models.identity import User
from app.schemas.identity import UserPreferencesUpdate, UserProfileUpdate, UserResponse


router = APIRouter(tags=["users"])


@router.patch("/users/me", response_model=UserResponse)
def update_my_profile(
    data: UserProfileUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update the caller's own name. Email + password go through dedicated endpoints."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        user.name = name
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/me/preferences")
def get_my_preferences(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.preferences or {}


_MAX_PREFERENCES_BYTES = 16 * 1024  # 16 KiB ceiling per-user


@router.patch("/users/me/preferences")
def update_my_preferences(
    data: UserPreferencesUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    current = dict(user.preferences or {})
    current.update(data.preferences)
    # Reject runaway prefs blobs before they hit the column.
    import json as _json
    if len(_json.dumps(current)) > _MAX_PREFERENCES_BYTES:
        raise HTTPException(status_code=413, detail="Preferences payload too large")
    user.preferences = current
    # SQLAlchemy doesn't always detect mutation of a JSON column's contents.
    flag_modified(user, "preferences")
    db.commit()
    return user.preferences
