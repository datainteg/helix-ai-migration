"""Redis client — single shared connection pool."""

import logging
import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    """Return shared Redis client, or None if unavailable."""
    global _client
    if _client is None:
        try:
            _client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            _client.ping()
        except Exception as exc:
            logger.warning("Redis unavailable — token revocation disabled: %s", exc)
            _client = None
    return _client
