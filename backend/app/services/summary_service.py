"""Precomputed daily report rows (M11).

``compute_day`` rebuilds one UTC day of ``daily_platform_summaries`` and
``daily_trainer_summaries`` from the source tables and upserts them, so it
can run any number of times. The ARQ worker (``app.worker``) runs it every
night for the previous day and hourly for today; reports read only these
tables plus ``daily_activity``.

Definitions (all by UTC day):

* sessions_held: completed sessions that started that day.
* attendance_*: attendance rows of sessions that started that day.
* submissions: submissions handed in that day.
* puzzle_attempts / puzzles_solved: attempts made that day. For a trainer,
  only attempts on that trainer's assignments.
* active_students: students with recorded activity that day. For a
  trainer, students who attempted that trainer's assignments.
* xp_awarded: XP events created that day.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    ClassSession,
    DailyActivity,
    DailyPlatformSummary,
    DailyTrainerSummary,
    PuzzleAttempt,
    SessionAttendance,
    Submission,
    TrainerProfile,
    User,
    XPEvent,
)

ATTENDANCE_STATUSES = ("present", "late", "absent", "excused")
MAX_RANGE_DAYS = 366


def _bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _attendance_counts(db: Session, start, end, trainer_id=None) -> dict:
    query = (
        select(SessionAttendance.status, func.count())
        .join(ClassSession, ClassSession.id == SessionAttendance.session_id)
        .where(
            ClassSession.start_time >= start,
            ClassSession.start_time < end,
            ClassSession.status != "cancelled",
            SessionAttendance.status.in_(ATTENDANCE_STATUSES),
        )
        .group_by(SessionAttendance.status)
    )
    if trainer_id is not None:
        query = query.where(ClassSession.trainer_id == trainer_id)
    counts = dict(db.execute(query).all())
    return {f"attendance_{status}": counts.get(status, 0) for status in ATTENDANCE_STATUSES}


def _platform_row(db: Session, day: date) -> dict:
    start, end = _bounds(day)

    def count(query):
        return db.scalar(query) or 0

    new_users = dict(
        db.execute(
            select(User.role, func.count())
            .where(User.created_at >= start, User.created_at < end)
            .group_by(User.role)
        ).all()
    )
    attempts = db.execute(
        select(func.count(), func.count().filter(PuzzleAttempt.is_solved.is_(True))).where(
            PuzzleAttempt.attempted_at >= start, PuzzleAttempt.attempted_at < end
        )
    ).one()

    return {
        "summary_date": day,
        "new_students": new_users.get("student", 0),
        "new_trainers": new_users.get("trainer", 0),
        "active_students": count(
            select(func.count(func.distinct(DailyActivity.student_id))).where(
                DailyActivity.activity_date == day,
                (DailyActivity.puzzles_attempted + DailyActivity.games_played) > 0,
            )
        ),
        "sessions_held": count(
            select(func.count()).where(
                ClassSession.status == "completed",
                ClassSession.start_time >= start,
                ClassSession.start_time < end,
            )
        ),
        **_attendance_counts(db, start, end),
        "submissions": count(
            select(func.count()).where(Submission.submitted_at >= start, Submission.submitted_at < end)
        ),
        "puzzle_attempts": attempts[0],
        "puzzles_solved": attempts[1],
        "xp_awarded": count(
            select(func.coalesce(func.sum(XPEvent.points), 0)).where(
                XPEvent.created_at >= start, XPEvent.created_at < end
            )
        ),
    }


def _trainer_rows(db: Session, day: date) -> list[dict]:
    start, end = _bounds(day)
    rows = []

    sessions = dict(
        db.execute(
            select(ClassSession.trainer_id, func.count())
            .where(
                ClassSession.status == "completed",
                ClassSession.start_time >= start,
                ClassSession.start_time < end,
            )
            .group_by(ClassSession.trainer_id)
        ).all()
    )
    submissions = dict(
        db.execute(
            select(Assignment.trainer_id, func.count())
            .select_from(Submission)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .where(Submission.submitted_at >= start, Submission.submitted_at < end)
            .group_by(Assignment.trainer_id)
        ).all()
    )
    attempts = {
        row.trainer_id: row
        for row in db.execute(
            select(
                Assignment.trainer_id,
                func.count().label("attempts"),
                func.count().filter(PuzzleAttempt.is_solved.is_(True)).label("solved"),
                func.count(func.distinct(PuzzleAttempt.student_id)).label("students"),
            )
            .select_from(PuzzleAttempt)
            .join(Assignment, Assignment.id == PuzzleAttempt.assignment_id)
            .where(PuzzleAttempt.attempted_at >= start, PuzzleAttempt.attempted_at < end)
            .group_by(Assignment.trainer_id)
        )
    }

    for trainer_id in db.scalars(select(TrainerProfile.id)):
        attempt = attempts.get(trainer_id)
        rows.append(
            {
                "trainer_id": trainer_id,
                "summary_date": day,
                "sessions_held": sessions.get(trainer_id, 0),
                **_attendance_counts(db, start, end, trainer_id),
                "submissions": submissions.get(trainer_id, 0),
                "active_students": attempt.students if attempt else 0,
                "puzzle_attempts": attempt.attempts if attempt else 0,
                "puzzles_solved": attempt.solved if attempt else 0,
            }
        )

    return rows


def _upsert(db: Session, model, values: dict, keys: list[str]) -> None:
    statement = pg_insert(model).values(id=uuid.uuid4(), **values)
    updates = {
        name: statement.excluded[name] for name in values if name not in keys
    }
    updates["computed_at"] = func.now()
    updates["updated_at"] = func.now()
    db.execute(statement.on_conflict_do_update(index_elements=keys, set_=updates))


def compute_day(db: Session, day: date) -> dict:
    """Recompute and store one UTC day. Returns the platform row."""
    platform = _platform_row(db, day)
    _upsert(db, DailyPlatformSummary, platform, ["summary_date"])

    for row in _trainer_rows(db, day):
        _upsert(db, DailyTrainerSummary, row, ["trainer_id", "summary_date"])

    db.commit()
    return platform


def compute_range(db: Session, start: date, end: date) -> int:
    """Recompute every day from ``start`` to ``end`` inclusive."""
    if end < start:
        raise ValueError("end must not be before start")
    if (end - start).days >= MAX_RANGE_DAYS:
        raise ValueError(f"At most {MAX_RANGE_DAYS} days at a time.")

    day, done = start, 0
    while day <= end:
        compute_day(db, day)
        day += timedelta(days=1)
        done += 1
    return done
