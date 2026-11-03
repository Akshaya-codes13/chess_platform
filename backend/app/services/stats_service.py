"""Student performance metrics computed from stored records.

Every metric is derived from rows in the database (puzzle attempts,
assignment recipients, attendance, XP progress and badges); nothing is
cached or estimated. Functions take a list of students and run one grouped
query per metric family, so the cost does not grow with the student count.

Definitions (see docs/M5_TRAINER_MODULE.md):

- puzzles_attempted: distinct puzzles with at least one attempt.
- puzzles_solved: distinct puzzles with at least one solved attempt.
- accuracy_percent: solved attempts / all attempts * 100.
- assignments_received: the trainer's published or completed assignments
  the student is a recipient of (drafts and cancelled ones are excluded).
- assignments_completed: received assignments in which the student solved
  every assignment puzzle, counting only attempts linked to that assignment.
- assignment_completion_rate: assignments_completed / assignments_received.
- attendance_rate: (present + late) / (present + late + absent) over the
  trainer's non-cancelled sessions; 'excused' and unrecorded are excluded.

Percentages are rounded to one decimal and are ``None`` when the
denominator is zero, so "no data" is never reported as 0%.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, and_, case, cast, func, select
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    AssignmentPuzzle,
    AssignmentRecipient,
    Badge,
    ClassSession,
    Puzzle,
    PuzzleAttempt,
    SessionAttendance,
    StudentBadge,
    StudentProgress,
)

RECEIVED_ASSIGNMENT_STATUSES = ("published", "completed")
ATTENDED_STATUSES = ("present", "late")
COUNTED_ATTENDANCE_STATUSES = ("present", "late", "absent")


def percent(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator * 100 / denominator, 1)


def _empty_metrics() -> dict:
    return {
        "puzzles_attempted": 0,
        "puzzles_solved": 0,
        "total_attempts": 0,
        "solved_attempts": 0,
        "accuracy_percent": None,
        "last_attempt_at": None,
        "assignments_received": 0,
        "assignments_completed": 0,
        "assignment_completion_rate": None,
        "sessions_recorded": 0,
        "sessions_attended": 0,
        "attendance_rate": None,
        "total_xp": 0,
        "current_streak": 0,
        "longest_streak": 0,
        "badges_count": 0,
    }


def assignment_puzzle_totals():
    """Subquery: number of puzzles in each assignment."""
    return (
        select(
            AssignmentPuzzle.assignment_id,
            func.count().label("puzzles_total"),
        )
        .group_by(AssignmentPuzzle.assignment_id)
        .subquery()
    )


def assignment_attempt_progress():
    """Subquery: per (assignment, student), distinct assignment puzzles
    attempted and solved, using only attempts linked to that assignment."""
    return (
        select(
            PuzzleAttempt.assignment_id,
            PuzzleAttempt.student_id,
            func.count(PuzzleAttempt.puzzle_id.distinct()).label("attempted"),
            func.count(PuzzleAttempt.puzzle_id.distinct())
            .filter(PuzzleAttempt.is_solved.is_(True))
            .label("solved"),
            func.count().label("attempts"),
            func.max(PuzzleAttempt.attempted_at).label("last_attempt_at"),
        )
        .join(
            AssignmentPuzzle,
            and_(
                AssignmentPuzzle.assignment_id == PuzzleAttempt.assignment_id,
                AssignmentPuzzle.puzzle_id == PuzzleAttempt.puzzle_id,
            ),
        )
        .group_by(PuzzleAttempt.assignment_id, PuzzleAttempt.student_id)
        .subquery()
    )


def student_metrics(
    db: Session,
    trainer_id: uuid.UUID,
    student_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict]:
    """Return the metrics above for each student, keyed by student id."""
    metrics = {student_id: _empty_metrics() for student_id in student_ids}

    if not student_ids:
        return metrics

    attempt_rows = db.execute(
        select(
            PuzzleAttempt.student_id,
            func.count().label("total"),
            func.count().filter(PuzzleAttempt.is_solved.is_(True)).label("solved"),
            func.count(PuzzleAttempt.puzzle_id.distinct()).label("puzzles"),
            func.count(PuzzleAttempt.puzzle_id.distinct())
            .filter(PuzzleAttempt.is_solved.is_(True))
            .label("puzzles_solved"),
            func.max(PuzzleAttempt.attempted_at).label("last_at"),
        )
        .where(PuzzleAttempt.student_id.in_(student_ids))
        .group_by(PuzzleAttempt.student_id)
    )

    for row in attempt_rows:
        m = metrics[row.student_id]
        m["total_attempts"] = row.total
        m["solved_attempts"] = row.solved
        m["puzzles_attempted"] = row.puzzles
        m["puzzles_solved"] = row.puzzles_solved
        m["accuracy_percent"] = percent(row.solved, row.total)
        m["last_attempt_at"] = row.last_at

    totals = assignment_puzzle_totals()
    progress = assignment_attempt_progress()
    is_complete = and_(
        totals.c.puzzles_total > 0,
        func.coalesce(progress.c.solved, 0) >= totals.c.puzzles_total,
    )

    assignment_rows = db.execute(
        select(
            AssignmentRecipient.student_id,
            func.count().label("received"),
            func.sum(cast(case((is_complete, 1), else_=0), Integer)).label("completed"),
        )
        .join(Assignment, Assignment.id == AssignmentRecipient.assignment_id)
        .outerjoin(totals, totals.c.assignment_id == Assignment.id)
        .outerjoin(
            progress,
            and_(
                progress.c.assignment_id == Assignment.id,
                progress.c.student_id == AssignmentRecipient.student_id,
            ),
        )
        .where(
            AssignmentRecipient.student_id.in_(student_ids),
            Assignment.trainer_id == trainer_id,
            Assignment.status.in_(RECEIVED_ASSIGNMENT_STATUSES),
        )
        .group_by(AssignmentRecipient.student_id)
    )

    for row in assignment_rows:
        m = metrics[row.student_id]
        m["assignments_received"] = row.received
        m["assignments_completed"] = row.completed or 0
        m["assignment_completion_rate"] = percent(m["assignments_completed"], row.received)

    attendance_rows = db.execute(
        select(
            SessionAttendance.student_id,
            func.count()
            .filter(SessionAttendance.status.in_(COUNTED_ATTENDANCE_STATUSES))
            .label("recorded"),
            func.count()
            .filter(SessionAttendance.status.in_(ATTENDED_STATUSES))
            .label("attended"),
        )
        .join(ClassSession, ClassSession.id == SessionAttendance.session_id)
        .where(
            SessionAttendance.student_id.in_(student_ids),
            ClassSession.trainer_id == trainer_id,
            ClassSession.status != "cancelled",
        )
        .group_by(SessionAttendance.student_id)
    )

    for row in attendance_rows:
        m = metrics[row.student_id]
        m["sessions_recorded"] = row.recorded
        m["sessions_attended"] = row.attended
        m["attendance_rate"] = percent(row.attended, row.recorded)

    for progress_row in db.scalars(
        select(StudentProgress).where(StudentProgress.student_id.in_(student_ids))
    ):
        m = metrics[progress_row.student_id]
        m["total_xp"] = progress_row.total_xp
        m["current_streak"] = progress_row.current_streak
        m["longest_streak"] = progress_row.longest_streak

    badge_rows = db.execute(
        select(StudentBadge.student_id, func.count().label("badges"))
        .where(StudentBadge.student_id.in_(student_ids))
        .group_by(StudentBadge.student_id)
    )

    for row in badge_rows:
        metrics[row.student_id]["badges_count"] = row.badges

    return metrics


def aggregate_metrics(per_student: dict[uuid.UUID, dict]) -> dict:
    """Combine per-student metrics into group totals.

    Rates are recomputed from the summed numerators and denominators, not
    averaged, so a student with many attempts weighs accordingly.
    """
    total_attempts = sum(m["total_attempts"] for m in per_student.values())
    solved_attempts = sum(m["solved_attempts"] for m in per_student.values())
    received = sum(m["assignments_received"] for m in per_student.values())
    completed = sum(m["assignments_completed"] for m in per_student.values())
    recorded = sum(m["sessions_recorded"] for m in per_student.values())
    attended = sum(m["sessions_attended"] for m in per_student.values())

    return {
        "student_count": len(per_student),
        "active_students": sum(1 for m in per_student.values() if m["total_attempts"]),
        "total_attempts": total_attempts,
        "solved_attempts": solved_attempts,
        "accuracy_percent": percent(solved_attempts, total_attempts),
        "assignments_received": received,
        "assignments_completed": completed,
        "assignment_completion_rate": percent(completed, received),
        "sessions_recorded": recorded,
        "sessions_attended": attended,
        "attendance_rate": percent(attended, recorded),
        "total_xp": sum(m["total_xp"] for m in per_student.values()),
    }


def weekly_progress(
    db: Session,
    student_id: uuid.UUID,
    weeks: int = 12,
) -> list[dict]:
    """Attempts, solves and accuracy per ISO week for the last ``weeks``.

    Weeks with no attempts are included with zero counts so the series is
    continuous; weeks are Monday-based in UTC.
    """
    today = datetime.now(timezone.utc).date()
    first_week = today - timedelta(days=today.weekday(), weeks=weeks - 1)
    since = datetime.combine(first_week, datetime.min.time(), tzinfo=timezone.utc)

    week = func.date_trunc("week", func.timezone("UTC", PuzzleAttempt.attempted_at))
    rows = db.execute(
        select(
            week.label("week"),
            func.count().label("attempts"),
            func.count().filter(PuzzleAttempt.is_solved.is_(True)).label("solved"),
        )
        .where(
            PuzzleAttempt.student_id == student_id,
            PuzzleAttempt.attempted_at >= since,
        )
        .group_by(week)
    )

    by_week = defaultdict(lambda: (0, 0))
    for row in rows:
        by_week[row.week.date()] = (row.attempts, row.solved)

    series = []
    for index in range(weeks):
        week_start = first_week + timedelta(weeks=index)
        attempts, solved = by_week[week_start]
        series.append({
            "week_start": week_start,
            "attempts": attempts,
            "solved": solved,
            "accuracy_percent": percent(solved, attempts),
        })

    return series


def student_badges(db: Session, student_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Badge.code, Badge.name, Badge.description, StudentBadge.earned_at)
        .join(StudentBadge, StudentBadge.badge_id == Badge.id)
        .where(StudentBadge.student_id == student_id)
        .order_by(StudentBadge.earned_at.desc())
    )
    return [row._asdict() for row in rows]


def recent_attempts(
    db: Session,
    student_ids: list[uuid.UUID],
    limit: int = 10,
):
    """Most recent puzzle attempts of the given students, newest first."""
    if not student_ids:
        return []

    return db.execute(
        select(
            PuzzleAttempt.id,
            PuzzleAttempt.student_id,
            PuzzleAttempt.puzzle_id,
            PuzzleAttempt.assignment_id,
            PuzzleAttempt.is_solved,
            PuzzleAttempt.time_taken_seconds,
            PuzzleAttempt.attempted_at,
            Puzzle.rating.label("puzzle_rating"),
            Puzzle.difficulty.label("puzzle_difficulty"),
        )
        .join(Puzzle, Puzzle.id == PuzzleAttempt.puzzle_id)
        .where(PuzzleAttempt.student_id.in_(student_ids))
        .order_by(PuzzleAttempt.attempted_at.desc())
        .limit(limit)
    ).all()
