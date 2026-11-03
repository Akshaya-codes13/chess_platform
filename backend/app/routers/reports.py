"""Reports built from the precomputed daily summary tables (M11)."""

import logging

import redis
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_admin
from app.models import TrainerProfile, User
from app.routers.trainer import current_trainer
from app.schemas.reports import AdminDailyReport, TrainerDailyReport
from app.services import daily_report_service, summary_service
from app.services.streak_service import today_utc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Reports"])

REFRESH_JOB_ID = "daily-summary-refresh"


class RefreshResult(BaseModel):
    queued: bool
    computed_inline: bool
    job_id: str | None = None


@router.get("/admin/reports/daily", response_model=AdminDailyReport)
def admin_daily_report(
    days: int = Query(30, ge=7, le=180),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Academy totals per day, per-trainer totals and student consistency."""
    return daily_report_service.admin_daily_report(db, days)


@router.post("/admin/reports/daily/refresh", response_model=RefreshResult, status_code=202)
async def refresh_daily_report(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Queue a recompute of yesterday and today on the ARQ worker. If the
    queue is unreachable, today is recomputed in this request instead."""
    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url), retry=0)
        try:
            job = await pool.enqueue_job("compute_daily_summaries", _job_id=REFRESH_JOB_ID)
        finally:
            await pool.aclose()
        return {"queued": True, "computed_inline": False, "job_id": job.job_id if job else REFRESH_JOB_ID}
    except (OSError, redis.RedisError) as exc:
        logger.warning("Job queue unavailable (%s); computing today inline.", exc)
        summary_service.compute_day(db, today_utc())
        return {"queued": False, "computed_inline": True}


@router.get("/trainer/reports/daily", response_model=TrainerDailyReport)
def trainer_daily_report(
    days: int = Query(30, ge=7, le=180),
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """The trainer's sessions, attendance, submissions and student consistency."""
    return daily_report_service.trainer_daily_report(db, trainer, days)
