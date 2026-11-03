"""Trainer profile, assigned groups, students, performance and dashboard."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    AssignmentRecipient,
    ClassSession,
    Group,
    GroupMember,
    Puzzle,
    PuzzleAttempt,
    SessionAttendance,
    StudentProfile,
    TrainerProfile,
    User,
)
from app.services import assignment_service, session_service, stats_service
from app.services.stats_service import (
    RECEIVED_ASSIGNMENT_STATUSES,
    assignment_attempt_progress,
    assignment_puzzle_totals,
    percent,
)
from app.services.trainer_access import (
    accessible_student_ids,
    get_accessible_student,
    get_owned_group,
    like_pattern,
)
from app.utils.pagination import PageParams, make_page, paginate

DASHBOARD_WINDOW_DAYS = 30

STUDENT_SORTS = {
    "name": User.full_name.asc(),
    "-name": User.full_name.desc(),
    "rating": StudentProfile.chess_rating.asc(),
    "-rating": StudentProfile.chess_rating.desc(),
    "joined": GroupMember.created_at.asc(),
    "-joined": GroupMember.created_at.desc(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Profile

def profile_response(db: Session, trainer: TrainerProfile) -> dict:
    user = db.get(User, trainer.user_id)
    return {
        "user_id": user.id,
        "trainer_profile_id": trainer.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "language": user.language,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "bio": trainer.bio,
        "specialization": trainer.specialization,
        "experience_years": trainer.experience_years,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


USER_PROFILE_FIELDS = ("full_name", "phone", "avatar_url", "language")
TRAINER_PROFILE_FIELDS = ("bio", "specialization", "experience_years")


def update_profile(db: Session, trainer: TrainerProfile, changes: dict) -> dict:
    """Apply permitted profile changes. The schema forbids every other field,
    so role, status and email cannot be changed here."""
    user = db.get(User, trainer.user_id)

    for field in USER_PROFILE_FIELDS:
        if field in changes:
            value = changes[field]
            if field == "full_name":
                if not value or not value.strip():
                    continue
                value = value.strip()
            if field == "language" and not value:
                continue
            setattr(user, field, value)

    for field in TRAINER_PROFILE_FIELDS:
        if field in changes:
            if field == "experience_years" and changes[field] is None:
                continue
            setattr(trainer, field, changes[field])

    db.commit()
    return profile_response(db, trainer)


# Groups

def _member_counts():
    return (
        select(GroupMember.group_id, func.count().label("student_count"))
        .group_by(GroupMember.group_id)
        .subquery()
    )


def _group_summary(group: Group, student_count: int) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "is_active": group.is_active,
        "student_count": student_count,
        "created_at": group.created_at,
    }


def _groups_query(trainer: TrainerProfile):
    counts = _member_counts()
    return (
        select(Group, func.coalesce(counts.c.student_count, 0).label("student_count"))
        .outerjoin(counts, counts.c.group_id == Group.id)
        .where(Group.trainer_id == trainer.id)
    )


def list_groups(
    db: Session,
    trainer: TrainerProfile,
    params: PageParams,
    *,
    search: str | None = None,
    is_active: bool | None = None,
) -> dict:
    query = _groups_query(trainer)

    if search and search.strip():
        query = query.where(Group.name.ilike(like_pattern(search)))
    if is_active is not None:
        query = query.where(Group.is_active.is_(is_active))

    rows, total = paginate(db, query.order_by(Group.name, Group.id), params)
    return make_page([_group_summary(row.Group, row.student_count) for row in rows], total, params)


def get_group(db: Session, trainer: TrainerProfile, group_id: uuid.UUID) -> dict:
    group = get_owned_group(db, trainer, group_id)
    now = _now()

    student_count = db.scalar(
        select(func.count()).where(GroupMember.group_id == group.id)
    ) or 0
    session_counts = db.execute(
        select(
            func.count().filter(
                ClassSession.start_time >= now,
                ClassSession.status.in_(session_service.ACTIVE_STATUSES),
            ).label("upcoming"),
            func.count().filter(ClassSession.status == "completed").label("completed"),
            func.min(ClassSession.start_time).filter(
                ClassSession.start_time >= now,
                ClassSession.status.in_(session_service.ACTIVE_STATUSES),
            ).label("next_at"),
        ).where(ClassSession.group_id == group.id, ClassSession.trainer_id == trainer.id)
    ).one()
    active_assignments = db.scalar(
        select(func.count()).where(
            Assignment.group_id == group.id,
            Assignment.trainer_id == trainer.id,
            Assignment.status == "published",
        )
    ) or 0

    return {
        **_group_summary(group, student_count),
        "upcoming_session_count": session_counts.upcoming,
        "completed_session_count": session_counts.completed,
        "active_assignment_count": active_assignments,
        "next_session_at": session_counts.next_at,
    }


def _student_row(profile: StudentProfile, user: User, joined_at: datetime) -> dict:
    return {
        "student_id": profile.id,
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "chess_rating": profile.chess_rating,
        "level": profile.level,
        "is_active": user.is_active,
        "joined_at": joined_at,
    }


def _group_students_query(group_id: uuid.UUID):
    return (
        select(StudentProfile, User, GroupMember.created_at.label("joined_at"))
        .join(GroupMember, GroupMember.student_id == StudentProfile.id)
        .join(User, User.id == StudentProfile.user_id)
        .where(GroupMember.group_id == group_id)
    )


def list_group_students(
    db: Session,
    trainer: TrainerProfile,
    group_id: uuid.UUID,
    params: PageParams,
    *,
    search: str | None = None,
    sort: str = "name",
) -> dict:
    group = get_owned_group(db, trainer, group_id)
    query = _group_students_query(group.id)

    if search and search.strip():
        pattern = like_pattern(search)
        query = query.where(User.full_name.ilike(pattern) | User.email.ilike(pattern))

    query = query.order_by(STUDENT_SORTS.get(sort, STUDENT_SORTS["name"]), StudentProfile.id)
    rows, total = paginate(db, query, params)

    return make_page(
        [_student_row(row.StudentProfile, row.User, row.joined_at) for row in rows],
        total,
        params,
    )


# Performance

def group_performance(db: Session, trainer: TrainerProfile, group_id: uuid.UUID) -> dict:
    group = get_owned_group(db, trainer, group_id)
    rows = db.execute(_group_students_query(group.id).order_by(User.full_name)).all()

    metrics = stats_service.student_metrics(
        db, trainer.id, [row.StudentProfile.id for row in rows]
    )

    return {
        "group": {"id": group.id, "name": group.name},
        "metrics": stats_service.aggregate_metrics(metrics),
        "students": [
            {
                **_student_row(row.StudentProfile, row.User, row.joined_at),
                "metrics": metrics[row.StudentProfile.id],
            }
            for row in rows
        ],
    }


def _student_assignments(db: Session, trainer: TrainerProfile, student_id: uuid.UUID) -> list[dict]:
    totals = assignment_puzzle_totals()
    progress = assignment_attempt_progress()

    rows = db.execute(
        select(
            Assignment.id,
            Assignment.title,
            Assignment.status,
            Assignment.due_date,
            func.coalesce(totals.c.puzzles_total, 0).label("puzzles_total"),
            func.coalesce(progress.c.solved, 0).label("puzzles_solved"),
        )
        .join(AssignmentRecipient, AssignmentRecipient.assignment_id == Assignment.id)
        .outerjoin(totals, totals.c.assignment_id == Assignment.id)
        .outerjoin(
            progress,
            and_(progress.c.assignment_id == Assignment.id, progress.c.student_id == student_id),
        )
        .where(
            AssignmentRecipient.student_id == student_id,
            Assignment.trainer_id == trainer.id,
            Assignment.status.in_(RECEIVED_ASSIGNMENT_STATUSES),
        )
        .order_by(Assignment.due_date.desc().nulls_last(), Assignment.created_at.desc())
        .limit(20)
    )

    return [
        {
            "assignment_id": row.id,
            "title": row.title,
            "status": row.status,
            "due_date": row.due_date,
            "puzzles_total": row.puzzles_total,
            "puzzles_solved": row.puzzles_solved,
            "completed": bool(row.puzzles_total and row.puzzles_solved >= row.puzzles_total),
        }
        for row in rows
    ]


def _attempt_activity(row, student_name: str | None = None) -> dict:
    rating = f" (rating {row.puzzle_rating})" if row.puzzle_rating else ""
    outcome = "Solved" if row.is_solved else "Attempted"
    return {
        "kind": "puzzle_attempt",
        "occurred_at": row.attempted_at,
        "description": f"{outcome} a puzzle{rating}",
        "student_id": row.student_id,
        "student_name": student_name,
        "is_solved": row.is_solved,
    }


def student_performance(db: Session, trainer: TrainerProfile, student_id: uuid.UUID) -> dict:
    student = get_accessible_student(db, trainer, student_id)
    user = db.get(User, student.user_id)

    groups = db.execute(
        select(Group.id, Group.name, GroupMember.created_at)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.student_id == student.id, Group.trainer_id == trainer.id)
        .order_by(Group.name)
    ).all()

    activity = [_attempt_activity(row) for row in stats_service.recent_attempts(db, [student.id])]

    attendance = db.execute(
        select(ClassSession.title, ClassSession.start_time, SessionAttendance.status)
        .join(SessionAttendance, SessionAttendance.session_id == ClassSession.id)
        .where(
            SessionAttendance.student_id == student.id,
            ClassSession.trainer_id == trainer.id,
            SessionAttendance.status != "scheduled",
        )
        .order_by(ClassSession.start_time.desc())
        .limit(5)
    )
    activity += [
        {
            "kind": "attendance",
            "occurred_at": row.start_time,
            "description": f"Marked {row.status} for “{row.title}”",
            "student_id": student.id,
        }
        for row in attendance
    ]
    activity.sort(key=lambda item: item["occurred_at"], reverse=True)

    return {
        "student": _student_row(student, user, min(row.created_at for row in groups)),
        "groups": [{"id": row.id, "name": row.name} for row in groups],
        "metrics": stats_service.student_metrics(db, trainer.id, [student.id])[student.id],
        "badges": stats_service.student_badges(db, student.id),
        "progress": stats_service.weekly_progress(db, student.id),
        "recent_activity": activity[:12],
        "assignments": _student_assignments(db, trainer, student.id),
    }


# Dashboard

def dashboard(db: Session, trainer: TrainerProfile) -> dict:
    now = _now()
    window_start = now - timedelta(days=DASHBOARD_WINDOW_DAYS)
    student_ids = list(db.scalars(accessible_student_ids(trainer).distinct()))

    group_rows = db.execute(_groups_query(trainer).order_by(Group.name)).all()

    session_counts = db.execute(
        select(
            func.count().filter(
                ClassSession.start_time >= now,
                ClassSession.status.in_(session_service.ACTIVE_STATUSES),
            ).label("upcoming"),
            func.count().filter(ClassSession.status == "completed").label("completed"),
        ).where(ClassSession.trainer_id == trainer.id)
    ).one()

    window_attempts = db.execute(
        select(
            func.count().label("attempts"),
            func.count().filter(PuzzleAttempt.is_solved.is_(True)).label("solved"),
            func.count(PuzzleAttempt.student_id.distinct()).label("active_students"),
        ).where(
            PuzzleAttempt.student_id.in_(student_ids),
            PuzzleAttempt.attempted_at >= window_start,
        )
    ).one() if student_ids else None

    overall = stats_service.aggregate_metrics(
        stats_service.student_metrics(db, trainer.id, student_ids)
    )

    names = dict(
        db.execute(
            select(StudentProfile.id, User.full_name)
            .join(User, User.id == StudentProfile.user_id)
            .where(StudentProfile.id.in_(student_ids))
        ).all()
    ) if student_ids else {}

    return {
        "profile": profile_response(db, trainer),
        "summary": {
            "group_count": len(group_rows),
            "student_count": len(student_ids),
            "puzzles_created": db.scalar(
                select(func.count()).where(Puzzle.created_by_trainer_id == trainer.id)
            ) or 0,
            "active_assignments": db.scalar(
                select(func.count()).where(
                    Assignment.trainer_id == trainer.id, Assignment.status == "published"
                )
            ) or 0,
            "upcoming_sessions": session_counts.upcoming,
            "completed_sessions": session_counts.completed,
        },
        "performance": {
            "window_days": DASHBOARD_WINDOW_DAYS,
            "attempts": window_attempts.attempts if window_attempts else 0,
            "solved": window_attempts.solved if window_attempts else 0,
            "accuracy_percent": (
                percent(window_attempts.solved, window_attempts.attempts) if window_attempts else None
            ),
            "active_students": window_attempts.active_students if window_attempts else 0,
            "assignment_completion_rate": overall["assignment_completion_rate"],
            "attendance_rate": overall["attendance_rate"],
        },
        "upcoming_sessions": session_service.upcoming_sessions(db, trainer),
        "recent_completed_sessions": session_service.recent_completed_sessions(db, trainer),
        "recent_assignments": assignment_service.recent_assignments(db, trainer),
        "groups": [_group_summary(row.Group, row.student_count) for row in group_rows],
        "recent_activity": [
            _attempt_activity(row, names.get(row.student_id))
            for row in stats_service.recent_attempts(db, student_ids)
        ],
    }
