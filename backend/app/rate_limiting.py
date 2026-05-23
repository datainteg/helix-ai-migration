"""Shared rate limiter instance — disabled in test/dev, active in production."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.APP_ENV == "production",
)
