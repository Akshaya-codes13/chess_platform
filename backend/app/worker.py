"""ARQ background worker: precomputes the daily report tables.

Run with ``arq app.worker.WorkerSettings`` (the ``worker`` service in
docker-compose.yml). Jobs:

* ``compute_daily_summaries`` — recompute a range of UTC days. Cron runs it
  at 00:15 UTC for yesterday (final numbers) and every hour for today.
* On startup, the last 30 days are backfilled if none were computed yet.
"""

import asyncio
import logging
from datetime import date, timedelta

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import DailyPlatformSummary
from app.services import summary_service
from app.services.streak_service import today_utc

logger = logging.getLogger(__name__)

BACKFILL_DAYS = 30


def _compute(start: date, end: date) -> int:
    with SessionLocal() as db:
        return summary_service.compute_range(db, start, end)


async def compute_daily_summaries(ctx, start: str | None = None, end: str | None = None) -> int:
    """Recompute ``start``..``end`` (ISO dates); defaults to yesterday and today."""
    today = today_utc()
    first = date.fromisoformat(start) if start else today - timedelta(days=1)
    last = date.fromisoformat(end) if end else today
    done = await asyncio.to_thread(_compute, first, last)
    logger.info("Daily summaries computed for %s days (%s..%s).", done, first, last)
    return done


async def refresh_today(ctx) -> int:
    today = today_utc().isoformat()
    return await compute_daily_summaries(ctx, today, today)


async def refresh_yesterday(ctx) -> int:
    yesterday = (today_utc() - timedelta(days=1)).isoformat()
    return await compute_daily_summaries(ctx, yesterday, yesterday)


def _has_summaries() -> bool:
    with SessionLocal() as db:
        return bool(db.scalar(select(func.count()).select_from(DailyPlatformSummary)))


async def startup(ctx) -> None:
    if not await asyncio.to_thread(_has_summaries):
        today = today_utc()
        await compute_daily_summaries(
            ctx, (today - timedelta(days=BACKFILL_DAYS - 1)).isoformat(), today.isoformat()
        )


class WorkerSettings:
    functions = [compute_daily_summaries]
    cron_jobs = [
        cron(refresh_yesterday, hour={0}, minute={15}),
        cron(refresh_today, minute={5}),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # One job at a time: the jobs write the same rows.
    max_jobs = 1
