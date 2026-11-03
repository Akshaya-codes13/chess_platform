"""Read-mostly platform oversight for admins: dashboard, puzzles and reports.

Every figure is computed from stored records; nothing is estimated.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Assignment,
    AssignmentPuzzle,
    AssignmentRecipient,
    AuditLog,
    Badge,
    ClassSession,
    Game,
    Group,
    Puzzle,
    PuzzleAttempt,
    PuzzleCategory,
    PuzzleTheme,
    PuzzleThemeMapping,
    SessionAttendance,
    StudentBadge,
    StudentProfile,
    StudentProgress,
    Submission,
    TrainerProfile,
    User,
)
from app.services.admin_service import (
    AdminContext,
    group_rows_stmt,
    group_summary,
    like_pattern,
    record_audit,
    user_ref,
)
from app.services.chess_validation import validate_puzzle_solution
from app.utils.pagination import PageParams, build_page, count_rows

RECENT_ACTIVITY_LIMIT = 10
RECENT_USERS_LIMIT = 5
TOP_GROUPS_LIMIT = 5
TOP_STUDENTS_LIMIT = 5

# Admin moderation of any puzzle: action -> (allowed current statuses, new status).
PUZZLE_ADMIN_TRANSITIONS = {
    "publish": ({"draft", "archived"}, "published"),
    "archive": ({"draft", "published"}, "archived"),
}
PUZZLE_AUDIT_ACTIONS = {"publish": "puzzle.published", "archive": "puzzle.archived"}


def _counts_by(db: Session, column) -> dict[str, int]:
    return {
        key: count
        for key, count in db.execute(select(column, func.count()).group_by(column))
        if key is not None
    }


def _activity_stmt():
    return (
        select(AuditLog, User.id.label("actor_id"), User.full_name, User.email)
        .outerjoin(User, User.id == AuditLog.actor_id)
    )


def _activity_item(row) -> dict:
    log = row.AuditLog
    return {
        "id": log.id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "actor": user_ref(row.actor_id, row.full_name, row.email),
        "details": log.details or {},
        "occurred_at": log.occurred_at,
    }


# ----- Dashboard -----------------------------------------------------------


def get_dashboard(db: Session) -> dict:
    now = datetime.now(timezone.utc)

    users = db.execute(
        select(
            func.count(),
            func.count().filter(User.is_active.is_(True)),
            func.count().filter(User.role == "admin"),
            func.count().filter(User.role == "trainer"),
            func.count().filter(User.role == "student"),
        ).select_from(User)
    ).one()

    groups = db.execute(
        select(func.count(), func.count().filter(Group.is_active.is_(True))).select_from(Group)
    ).one()

    sessions = db.execute(
        select(
            func.count(),
            func.count().filter(
                ClassSession.status == "scheduled", ClassSession.start_time > now
            ),
            func.count().filter(ClassSession.status == "completed"),
        ).select_from(ClassSession)
    ).one()

    assignments_by_status = _counts_by(db, Assignment.status)

    recent_activity = db.execute(
        _activity_stmt()
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id)
        .limit(RECENT_ACTIVITY_LIMIT)
    ).all()

    recent_users = db.scalars(
        select(User).order_by(User.created_at.desc(), User.id).limit(RECENT_USERS_LIMIT)
    ).all()

    groups_stmt = group_rows_stmt().where(Group.is_active.is_(True))
    top_groups = db.execute(
        groups_stmt.order_by(groups_stmt.selected_columns.member_count.desc(), Group.name)
        .limit(TOP_GROUPS_LIMIT)
    ).all()

    return {
        "users": {
            "total": users[0],
            "active": users[1],
            "inactive": users[0] - users[1],
            "admins": users[2],
            "trainers": users[3],
            "students": users[4],
        },
        "groups": {"total": groups[0], "active": groups[1]},
        "puzzles": db.scalar(select(func.count()).select_from(Puzzle)),
        "assignments": {
            "total": sum(assignments_by_status.values()),
            "by_status": assignments_by_status,
        },
        "sessions": {"total": sessions[0], "upcoming": sessions[1], "completed": sessions[2]},
        "recent_activity": [_activity_item(row) for row in recent_activity],
        "recent_users": list(recent_users),
        "top_groups": [group_summary(row) for row in top_groups],
    }


def list_activity(
    db: Session,
    params: PageParams,
    entity_type: str | None = None,
    action: str | None = None,
) -> dict:
    stmt = _activity_stmt()
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)

    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id)
        .offset(params.offset)
        .limit(params.page_size)
    ).all()

    return build_page([_activity_item(row) for row in rows], total, params)


# ----- Puzzles -------------------------------------------------------------


def _puzzle_stmt():
    author = aliased(User)
    return (
        select(
            Puzzle,
            PuzzleCategory.id.label("category_id"),
            PuzzleCategory.name.label("category_name"),
            PuzzleCategory.slug.label("category_slug"),
            author.id.label("author_id"),
            author.full_name.label("author_name"),
            author.email.label("author_email"),
        )
        .outerjoin(PuzzleCategory, PuzzleCategory.id == Puzzle.category_id)
        .outerjoin(TrainerProfile, TrainerProfile.id == Puzzle.created_by_trainer_id)
        .outerjoin(author, author.id == TrainerProfile.user_id)
    )


def _themes_for(db: Session, puzzle_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    themes = defaultdict(list)
    if not puzzle_ids:
        return themes

    rows = db.execute(
        select(PuzzleThemeMapping.puzzle_id, PuzzleTheme.id, PuzzleTheme.name, PuzzleTheme.slug)
        .join(PuzzleTheme, PuzzleTheme.id == PuzzleThemeMapping.theme_id)
        .where(PuzzleThemeMapping.puzzle_id.in_(puzzle_ids))
        .order_by(PuzzleTheme.name)
    )
    for puzzle_id, theme_id, name, slug in rows:
        themes[puzzle_id].append({"id": theme_id, "name": name, "slug": slug})
    return themes


def puzzle_issues(puzzle: Puzzle, has_category: bool, themes: list) -> list[str]:
    """Describe what is wrong or missing in a puzzle record."""
    issues = []
    try:
        validate_puzzle_solution(puzzle.fen, puzzle.solution or "")
    except ValueError as exc:
        issues.append(str(exc))

    if not has_category:
        issues.append("No category.")
    if not themes:
        issues.append("No themes.")
    if puzzle.rating is None:
        issues.append("No rating.")
    return issues


def _puzzle_summary(row, themes: list[dict]) -> dict:
    puzzle = row.Puzzle
    return {
        "id": puzzle.id,
        "lichess_id": puzzle.lichess_id,
        "fen": puzzle.fen,
        "rating": puzzle.rating,
        "type": puzzle.type,
        "status": puzzle.status,
        "difficulty": puzzle.difficulty,
        "source": puzzle.source,
        "author": user_ref(row.author_id, row.author_name, row.author_email),
        "category": (
            {"id": row.category_id, "name": row.category_name, "slug": row.category_slug}
            if row.category_id
            else None
        ),
        "themes": themes,
        "issues": puzzle_issues(puzzle, row.category_id is not None, themes),
        "created_at": puzzle.created_at,
    }


def list_puzzles(
    db: Session,
    params: PageParams,
    search: str | None = None,
    status: str | None = None,
    category_id: uuid.UUID | None = None,
    theme_id: uuid.UUID | None = None,
    puzzle_type: str | None = None,
    source: str | None = None,
    min_rating: int | None = None,
    max_rating: int | None = None,
    incomplete_only: bool = False,
) -> dict:
    stmt = _puzzle_stmt()

    if search and search.strip():
        pattern = like_pattern(search.strip())
        stmt = stmt.where(
            or_(
                Puzzle.lichess_id.ilike(pattern, escape="\\"),
                Puzzle.explanation.ilike(pattern, escape="\\"),
                Puzzle.difficulty.ilike(pattern, escape="\\"),
            )
        )
    if status:
        stmt = stmt.where(Puzzle.status == status)
    if category_id:
        stmt = stmt.where(Puzzle.category_id == category_id)
    if theme_id:
        stmt = stmt.where(
            exists().where(
                PuzzleThemeMapping.puzzle_id == Puzzle.id,
                PuzzleThemeMapping.theme_id == theme_id,
            )
        )
    if puzzle_type:
        stmt = stmt.where(Puzzle.type == puzzle_type)
    if source:
        stmt = stmt.where(Puzzle.source == source)
    if min_rating is not None:
        stmt = stmt.where(Puzzle.rating >= min_rating)
    if max_rating is not None:
        stmt = stmt.where(Puzzle.rating <= max_rating)
    if incomplete_only:
        # Checks that SQL can make over the whole table. Chess legality is
        # verified per row and reported in ``issues``.
        stmt = stmt.where(
            or_(
                Puzzle.category_id.is_(None),
                Puzzle.rating.is_(None),
                func.trim(Puzzle.solution) == "",
                ~exists().where(PuzzleThemeMapping.puzzle_id == Puzzle.id),
            )
        )

    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(Puzzle.created_at.desc(), Puzzle.id)
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    themes = _themes_for(db, [row.Puzzle.id for row in rows])

    return build_page([_puzzle_summary(row, themes[row.Puzzle.id]) for row in rows], total, params)


def get_puzzle_detail(db: Session, puzzle_id: uuid.UUID) -> dict:
    row = db.execute(_puzzle_stmt().where(Puzzle.id == puzzle_id)).first()
    if row is None:
        raise NotFoundError("Puzzle not found.")

    puzzle = row.Puzzle
    attempts, solved = db.execute(
        select(func.count(), func.count().filter(PuzzleAttempt.is_solved.is_(True))).where(
            PuzzleAttempt.puzzle_id == puzzle_id
        )
    ).one()

    return {
        **_puzzle_summary(row, _themes_for(db, [puzzle_id])[puzzle_id]),
        "solution": puzzle.solution,
        "explanation": puzzle.explanation,
        "rating_deviation": puzzle.rating_deviation,
        "popularity": puzzle.popularity,
        "usage": {
            "assignment_count": db.scalar(
                select(func.count()).where(AssignmentPuzzle.puzzle_id == puzzle_id)
            ),
            "attempt_count": attempts,
            "solved_count": solved,
        },
    }


def change_puzzle_status(db: Session, ctx: AdminContext, puzzle_id: uuid.UUID, action: str) -> dict:
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise NotFoundError("Puzzle not found.")

    allowed, new_status = PUZZLE_ADMIN_TRANSITIONS[action]
    if puzzle.status not in allowed:
        raise ConflictError(f"Cannot {action} a puzzle that is {puzzle.status}.")

    if new_status == "published":
        try:
            validate_puzzle_solution(puzzle.fen, puzzle.solution or "")
        except ValueError as exc:
            raise ValidationError(f"This puzzle cannot be published: {exc}")

    previous = puzzle.status
    puzzle.status = new_status
    record_audit(
        db, ctx, PUZZLE_AUDIT_ACTIONS[action], "puzzle", puzzle.id,
        {"from": previous, "to": new_status},
    )
    db.commit()

    return get_puzzle_detail(db, puzzle.id)


def puzzle_filter_options(db: Session) -> dict:
    def distinct(column):
        return [value for value in db.scalars(select(column).distinct().order_by(column)) if value]

    return {
        "categories": [
            {"id": c.id, "name": c.name, "slug": c.slug}
            for c in db.scalars(select(PuzzleCategory).order_by(PuzzleCategory.name))
        ],
        "themes": [
            {"id": t.id, "name": t.name, "slug": t.slug}
            for t in db.scalars(select(PuzzleTheme).order_by(PuzzleTheme.name))
        ],
        "types": distinct(Puzzle.type),
        "sources": distinct(Puzzle.source),
        "statuses": distinct(Puzzle.status),
    }


# ----- Assignments and sessions --------------------------------------------


def list_assignments(
    db: Session,
    params: PageParams,
    search: str | None = None,
    status: str | None = None,
    trainer_user_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
) -> dict:
    trainer_user = aliased(User)

    def counted(key):
        return (
            select(key.label("assignment_id"), func.count().label("n"))
            .group_by(key)
            .subquery()
        )

    recipients = counted(AssignmentRecipient.assignment_id)
    submissions = counted(Submission.assignment_id)
    puzzles = counted(AssignmentPuzzle.assignment_id)

    stmt = (
        select(
            Assignment,
            trainer_user.id.label("trainer_id"),
            trainer_user.full_name.label("trainer_name"),
            trainer_user.email.label("trainer_email"),
            Group.id.label("group_id"),
            Group.name.label("group_name"),
            Group.is_active.label("group_active"),
            func.coalesce(recipients.c.n, 0).label("recipient_count"),
            func.coalesce(submissions.c.n, 0).label("submission_count"),
            func.coalesce(puzzles.c.n, 0).label("puzzle_count"),
        )
        .join(TrainerProfile, TrainerProfile.id == Assignment.trainer_id)
        .join(trainer_user, trainer_user.id == TrainerProfile.user_id)
        .outerjoin(Group, Group.id == Assignment.group_id)
        .outerjoin(recipients, recipients.c.assignment_id == Assignment.id)
        .outerjoin(submissions, submissions.c.assignment_id == Assignment.id)
        .outerjoin(puzzles, puzzles.c.assignment_id == Assignment.id)
    )

    if search and search.strip():
        stmt = stmt.where(Assignment.title.ilike(like_pattern(search.strip()), escape="\\"))
    if status:
        stmt = stmt.where(Assignment.status == status)
    if trainer_user_id:
        stmt = stmt.where(trainer_user.id == trainer_user_id)
    if group_id:
        stmt = stmt.where(Assignment.group_id == group_id)

    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(Assignment.created_at.desc(), Assignment.id)
        .offset(params.offset)
        .limit(params.page_size)
    ).all()

    items = [
        {
            "id": row.Assignment.id,
            "title": row.Assignment.title,
            "status": row.Assignment.status,
            "assignment_type": row.Assignment.assignment_type,
            "due_date": row.Assignment.due_date,
            "published_at": row.Assignment.published_at,
            "trainer": user_ref(row.trainer_id, row.trainer_name, row.trainer_email),
            "group": (
                {"id": row.group_id, "name": row.group_name, "is_active": row.group_active}
                if row.group_id
                else None
            ),
            "recipient_count": row.recipient_count,
            "submission_count": row.submission_count,
            "puzzle_count": row.puzzle_count,
            "created_at": row.Assignment.created_at,
        }
        for row in rows
    ]
    return build_page(items, total, params)


def list_sessions(
    db: Session,
    params: PageParams,
    status: str | None = None,
    timeframe: str | None = None,
    trainer_user_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
) -> dict:
    trainer_user = aliased(User)
    now = datetime.now(timezone.utc)

    stmt = (
        select(
            ClassSession,
            trainer_user.id.label("trainer_id"),
            trainer_user.full_name.label("trainer_name"),
            trainer_user.email.label("trainer_email"),
            Group.id.label("group_id"),
            Group.name.label("group_name"),
            Group.is_active.label("group_active"),
        )
        .join(TrainerProfile, TrainerProfile.id == ClassSession.trainer_id)
        .join(trainer_user, trainer_user.id == TrainerProfile.user_id)
        .outerjoin(Group, Group.id == ClassSession.group_id)
    )

    if status:
        stmt = stmt.where(ClassSession.status == status)
    if timeframe == "upcoming":
        stmt = stmt.where(ClassSession.start_time > now)
    elif timeframe == "past":
        stmt = stmt.where(ClassSession.start_time <= now)
    if trainer_user_id:
        stmt = stmt.where(trainer_user.id == trainer_user_id)
    if group_id:
        stmt = stmt.where(ClassSession.group_id == group_id)

    order = (
        ClassSession.start_time.asc() if timeframe == "upcoming" else ClassSession.start_time.desc()
    )
    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(order, ClassSession.id).offset(params.offset).limit(params.page_size)
    ).all()

    attendance = defaultdict(dict)
    session_ids = [row.ClassSession.id for row in rows]
    if session_ids:
        for session_id, att_status, count in db.execute(
            select(SessionAttendance.session_id, SessionAttendance.status, func.count())
            .where(SessionAttendance.session_id.in_(session_ids))
            .group_by(SessionAttendance.session_id, SessionAttendance.status)
        ):
            attendance[session_id][att_status] = count

    items = [
        {
            "id": row.ClassSession.id,
            "title": row.ClassSession.title,
            "session_type": row.ClassSession.session_type,
            "status": row.ClassSession.status,
            "start_time": row.ClassSession.start_time,
            "end_time": row.ClassSession.end_time,
            "trainer": user_ref(row.trainer_id, row.trainer_name, row.trainer_email),
            "group": (
                {"id": row.group_id, "name": row.group_name, "is_active": row.group_active}
                if row.group_id
                else None
            ),
            "attendance": attendance[row.ClassSession.id],
        }
        for row in rows
    ]
    return build_page(items, total, params)


# ----- Reports -------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


def get_reports_overview(db: Session) -> dict:
    attendance = _counts_by(db, SessionAttendance.status)
    attended = attendance.get("present", 0) + attendance.get("late", 0)
    marked = attended + attendance.get("absent", 0) + attendance.get("excused", 0)

    attempts, solved = db.execute(
        select(func.count(), func.count().filter(PuzzleAttempt.is_solved.is_(True))).select_from(
            PuzzleAttempt
        )
    ).one()

    students_with_progress, total_xp, average_xp = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(StudentProgress.total_xp), 0),
            func.coalesce(func.avg(StudentProgress.total_xp), 0),
        ).select_from(StudentProgress)
    ).one()

    top_students = db.execute(
        select(
            User.id,
            User.full_name,
            StudentProgress.total_xp,
            StudentProgress.current_streak,
            StudentProgress.puzzles_solved,
        )
        .join(StudentProfile, StudentProfile.id == StudentProgress.student_id)
        .join(User, User.id == StudentProfile.user_id)
        .order_by(StudentProgress.total_xp.desc(), User.full_name)
        .limit(TOP_STUDENTS_LIMIT)
    ).all()

    return {
        "assignments_by_status": _counts_by(db, Assignment.status),
        "submissions_by_status": _counts_by(db, Submission.status),
        "sessions_by_status": _counts_by(db, ClassSession.status),
        "attendance_by_status": attendance,
        # Present or late, out of records that have been marked.
        "attendance_rate": _rate(attended, marked),
        "games": {
            "total": db.scalar(select(func.count()).select_from(Game)),
            "by_status": _counts_by(db, Game.status),
            "by_type": _counts_by(db, Game.game_type),
            "by_result": _counts_by(db, Game.result),
        },
        "puzzle_attempts": {
            "total": attempts,
            "solved": solved,
            "solve_rate": _rate(solved, attempts) or 0.0,
        },
        "gamification": {
            "students_with_progress": students_with_progress,
            "total_xp": int(total_xp),
            "average_xp": round(float(average_xp), 1),
            "badges_defined": db.scalar(select(func.count()).select_from(Badge)),
            "badges_awarded": db.scalar(select(func.count()).select_from(StudentBadge)),
            "top_students": [row._asdict() for row in top_students],
        },
    }
