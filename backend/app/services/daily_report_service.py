"""Admin and trainer reports read from the precomputed daily tables.

Nothing here scans the raw activity tables: the numbers come from
``daily_platform_summaries`` and ``daily_trainer_summaries`` (written by the
ARQ job) and from ``daily_activity`` (written as students practise). Days the
job has not computed yet are listed in ``missing_days`` instead of being
reported as zero.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    DailyActivity,
    DailyPlatformSummary,
    DailyTrainerSummary,
    Group,
    GroupMember,
    StudentProfile,
    TrainerProfile,
    User,
)
from app.services.streak_service import today_utc

COUNTERS = (
    "sessions_held",
    "attendance_present",
    "attendance_late",
    "attendance_absent",
    "attendance_excused",
    "submissions",
    "active_students",
    "puzzle_attempts",
    "puzzles_solved",
)
PLATFORM_COUNTERS = COUNTERS + ("new_students", "new_trainers", "xp_awarded")


def _percent(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def _attendance_rate(values: dict) -> float | None:
    attended = values["attendance_present"] + values["attendance_late"]
    return _percent(attended, attended + values["attendance_absent"])


def _window(days: int) -> tuple[date, date]:
    end = today_utc()
    return end - timedelta(days=days - 1), end


def _series(rows, start: date, end: date, counters) -> tuple[list[dict], list[date]]:
    by_day = {row.summary_date: row for row in rows}
    series, missing = [], []
    day = start

    while day <= end:
        row = by_day.get(day)
        if row is None:
            missing.append(day)
        series.append(
            {"date": day, "computed": row is not None, **{name: getattr(row, name, 0) if row else 0 for name in counters}}
        )
        day += timedelta(days=1)

    return series, missing


def _totals(series: list[dict], counters) -> dict:
    totals = {name: sum(point[name] for point in series) for name in counters}
    totals["attendance_rate"] = _attendance_rate(totals)
    totals["solve_rate"] = _percent(totals["puzzles_solved"], totals["puzzle_attempts"])
    return totals


def _student_consistency(db: Session, student_ids, start: date, end: date, days: int) -> list[dict]:
    if student_ids is not None and not student_ids:
        return []

    query = (
        select(
            StudentProfile.id,
            StudentProfile.user_id,
            User.full_name,
            func.count(DailyActivity.id).label("active_days"),
            func.coalesce(func.sum(DailyActivity.puzzles_solved), 0).label("solved"),
            func.coalesce(func.sum(DailyActivity.xp_earned), 0).label("xp"),
        )
        .join(User, User.id == StudentProfile.user_id)
        .outerjoin(
            DailyActivity,
            (DailyActivity.student_id == StudentProfile.id)
            & (DailyActivity.activity_date >= start)
            & (DailyActivity.activity_date <= end),
        )
        .where(User.is_active.is_(True))
        .group_by(StudentProfile.id, StudentProfile.user_id, User.full_name)
        .order_by(func.count(DailyActivity.id).desc(), User.full_name)
    )
    if student_ids is not None:
        query = query.where(StudentProfile.id.in_(student_ids))

    return [
        {
            "student_id": row.id,
            "user_id": row.user_id,
            "full_name": row.full_name,
            "active_days": row.active_days,
            "consistency_percent": _percent(row.active_days, days),
            "puzzles_solved": row.solved,
            "xp_earned": row.xp,
        }
        for row in db.execute(query.limit(100))
    ]


def admin_daily_report(db: Session, days: int) -> dict:
    start, end = _window(days)
    rows = db.scalars(
        select(DailyPlatformSummary).where(
            DailyPlatformSummary.summary_date >= start, DailyPlatformSummary.summary_date <= end
        )
    ).all()
    series, missing = _series(rows, start, end, PLATFORM_COUNTERS)

    trainer_totals = db.execute(
        select(
            TrainerProfile.id,
            User.full_name,
            *[func.coalesce(func.sum(getattr(DailyTrainerSummary, name)), 0).label(name) for name in COUNTERS],
        )
        .join(User, User.id == TrainerProfile.user_id)
        .outerjoin(
            DailyTrainerSummary,
            (DailyTrainerSummary.trainer_id == TrainerProfile.id)
            & (DailyTrainerSummary.summary_date >= start)
            & (DailyTrainerSummary.summary_date <= end),
        )
        .group_by(TrainerProfile.id, User.full_name)
        .order_by(User.full_name)
    ).all()

    trainers = []
    for row in trainer_totals:
        values = {name: getattr(row, name) for name in COUNTERS}
        trainers.append(
            {
                "trainer_id": row.id,
                "full_name": row.full_name,
                **values,
                "attendance_rate": _attendance_rate(values),
                "solve_rate": _percent(values["puzzles_solved"], values["puzzle_attempts"]),
            }
        )

    last_computed = db.scalar(select(func.max(DailyPlatformSummary.computed_at)))

    return {
        "start_date": start,
        "end_date": end,
        "days": days,
        "last_computed_at": last_computed,
        "missing_days": missing,
        "totals": _totals(series, PLATFORM_COUNTERS),
        "series": series,
        "trainers": trainers,
        "students": _student_consistency(db, None, start, end, days),
    }


def trainer_daily_report(db: Session, trainer: TrainerProfile, days: int) -> dict:
    start, end = _window(days)
    rows = db.scalars(
        select(DailyTrainerSummary).where(
            DailyTrainerSummary.trainer_id == trainer.id,
            DailyTrainerSummary.summary_date >= start,
            DailyTrainerSummary.summary_date <= end,
        )
    ).all()
    series, missing = _series(rows, start, end, COUNTERS)

    student_ids = set(
        db.scalars(select(StudentProfile.id).where(StudentProfile.trainer_id == trainer.id))
    ) | set(
        db.scalars(
            select(GroupMember.student_id)
            .join(Group, Group.id == GroupMember.group_id)
            .where(Group.trainer_id == trainer.id)
        )
    )
    last_computed = db.scalar(
        select(func.max(DailyTrainerSummary.computed_at)).where(DailyTrainerSummary.trainer_id == trainer.id)
    )

    return {
        "start_date": start,
        "end_date": end,
        "days": days,
        "last_computed_at": last_computed,
        "missing_days": missing,
        "totals": _totals(series, COUNTERS),
        "series": series,
        "students": _student_consistency(db, student_ids, start, end, days),
    }
