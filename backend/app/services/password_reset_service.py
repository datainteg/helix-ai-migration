"""Password reset: generate token, validate, apply new password."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.identity import User, PasswordResetToken
from app.auth.jwt import hash_password

logger = logging.getLogger(__name__)

_TOKEN_TTL_MINUTES = 30


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def request_password_reset(db: Session, email: str) -> str | None:
    """Create a reset token for the user. Returns raw token (caller sends via email).
    Returns None if email not found — caller should NOT reveal this to the client.
    """
    user = db.query(User).filter(User.email == email, User.status == "active").first()
    if not user:
        return None

    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_TOKEN_TTL_MINUTES)
    record = PasswordResetToken(
        user_id=str(user.id),
        token_hash=_hash_token(raw_token),
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    logger.info("password_reset_token_created user_id=%s", user.id)
    return raw_token


def confirm_password_reset(db: Session, raw_token: str, new_password: str) -> None:
    """Validate token and apply new password. Raises HTTPException on invalid/expired."""
    token_hash = _hash_token(raw_token)
    record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already-used reset token")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired")

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account not active")

    user.password_hash = hash_password(new_password)
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("password_reset_completed user_id=%s", user.id)
