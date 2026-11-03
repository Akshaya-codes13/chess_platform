"""Redis cache for student streaks.

``daily_activity`` stays the source of truth. After every recorded activity
the student's streak is written to ``streak:<student id>`` so profile and
dashboard reads do not have to scan their whole activity history. A missing
key or any Redis failure falls back to the database, so a cache outage never
changes what students see.
"""

import logging
import uuid
from datetime import date, timedelta

import redis

from app.core.rate_limit import redis_client

logger = logging.getLogger(__name__)

KEY_PREFIX = "streak"
# Long enough to survive a day without activity, after which the streak is 0
# anyway and is recomputed from the database.
TTL_SECONDS = 3 * 24 * 60 * 60


def cache_key(student_id: uuid.UUID) -> str:
    return f"{KEY_PREFIX}:{student_id}"


def store(student_id: uuid.UUID, current: int, longest: int, last_day: date) -> None:
    try:
        pipeline = redis_client.pipeline()
        pipeline.hset(
            cache_key(student_id),
            mapping={"current": current, "longest": longest, "last_day": last_day.isoformat()},
        )
        pipeline.expire(cache_key(student_id), TTL_SECONDS)
        pipeline.execute()
    except redis.RedisError:
        logger.warning("Streak cache unavailable; skipping write.")


def load(student_id: uuid.UUID, today: date) -> dict | None:
    """Return the cached streak as of ``today``, or None on a miss."""
    try:
        raw = redis_client.hgetall(cache_key(student_id))
    except redis.RedisError:
        logger.warning("Streak cache unavailable; reading from the database.")
        return None

    if not raw:
        return None

    try:
        values = {key.decode(): value.decode() for key, value in raw.items()}
        last_day = date.fromisoformat(values["last_day"])
        current = int(values["current"])
        longest = int(values["longest"])
    except (KeyError, ValueError):
        return None

    if last_day < today - timedelta(days=1):
        current = 0

    return {"current_streak": current, "longest_streak": longest, "last_activity_date": last_day}


def forget(student_id: uuid.UUID) -> None:
    try:
        redis_client.delete(cache_key(student_id))
    except redis.RedisError:
        pass
