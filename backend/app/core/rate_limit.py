import logging

import redis
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "ratelimit"

redis_client = redis.Redis.from_url(
    settings.redis_url,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def rate_limit_key(scope: str, client_host: str) -> str:
    return f"{KEY_PREFIX}:{scope}:{client_host}"


def rate_limit(scope: str):
    """Build a fixed-window, per-client-IP rate limit dependency.

    Limits come from settings at request time. If Redis is unavailable the
    request is allowed, so a cache outage does not lock users out.
    """

    def limiter(request: Request) -> None:
        if not settings.auth_rate_limit_enabled:
            return

        client_host = request.client.host if request.client else "unknown"
        key = rate_limit_key(scope, client_host)
        window = settings.auth_rate_limit_window_seconds

        try:
            pipeline = redis_client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, window, nx=True)
            pipeline.ttl(key)
            count, _, ttl = pipeline.execute()
        except redis.RedisError:
            logger.warning("Rate limiter unavailable; allowing request.")
            return

        if count > settings.auth_rate_limit_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(max(ttl, 1))},
            )

    return limiter
