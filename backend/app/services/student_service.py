"""Student module: read models and puzzle attempts for the signed-in student.

Every query is filtered by the caller's ``StudentProfile.id``. Resources the
student may not see (another student's assignment, a group they are not in,
a draft assignment) raise ``NotFoundError`` exactly like missing ones, so IDs
of other students' records cannot be probed.

Visibility rules:

* Assignments: the student is an ``AssignmentRecipient``, the assignment is
  ``published`` or ``completed`` (closed), and its ``start_date`` (if any)
  has passed. Drafts and cancelled assignments are hidden.
* Puzzles: only through a visible assignment that contains them.
* Sessions: group sessions of the student's groups, plus any session where
  the student has an attendance record (individual sessions for selected
  students create those records when they are scheduled).
* Groups: groups the student is a member of. Other members are only counted,
  never listed.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, distinct, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Assignment,
    AssignmentPuzzle,
    AssignmentRecipient,
    Badge,
    ClassSession,
    DailyActivity,
    Group,
    GroupMember,
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
    XPEvent,
)
from app.services import notification_service, puzzle_solver, streak_cache
from app.services.streak_service import active_streak, calculate_streaks, today_utc
from app.services.xp_service import (
    ASSIGNMENT_COMPLETED_XP,
    PUZZLE_SOLVED_XP,
    add_xp_event,
    award_earned_badges,
    badge_counters,
    level_for_xp,
    next_milestone,
)
from app.utils.pagination import PageParams, make_page, paginate_list

VISIBLE_ASSIGNMENT_STATUSES = ("published", "completed")
UPCOMING_SESSION_STATUSES = ("scheduled", "ongoing")

ASSIGNMENT_STATUSES = ("pending", "in_progress", "completed", "overdue")

METRIC_DEFINITIONS = {
    "puzzles_attempted": "Distinct puzzles you have attempted at least once.",
    "puzzles_solved": "Distinct puzzles you have solved at least once.",
    "accuracy_percent": "Solved attempts divided by all attempts, x100.",
    "average_solve_time_seconds": "Mean time of your solved attempts.",
    "assignment_completion_percent": (
        "Assignments in which every puzzle is solved, divided by all "
        "assignments you have received, x100."
    ),
    "current_streak": (
        "Consecutive UTC days with puzzle activity, ending today or "
        "yesterday. A missed day resets it to 0."
    ),
    "xp": (
        f"{PUZZLE_SOLVED_XP} XP the first time you solve each puzzle, plus "
        "each badge's reward when you earn it. Re-solving earns nothing."
    ),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _percent(part: int, whole: int) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


# --- Profile lookup ----------------------------------------------------------


def find_student_profile(db: Session, user: User) -> StudentProfile | None:
    return db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )


def get_access_status(db: Session, user: User) -> dict:
    """Report whether the student has a profile with an assigned trainer."""
    profile = find_student_profile(db, user)

    if profile is None or profile.trainer_id is None:
        return {"status": "awaiting_trainer", "trainer": None}

    trainer = _trainer_summaries(db, [profile.trainer_id]).get(profile.trainer_id)
    return {"status": "ready", "trainer": trainer}


def require_student_profile(db: Session, user: User) -> StudentProfile:
    profile = find_student_profile(db, user)

    if profile is None:
        raise NotFoundError(
            "Your student profile has not been set up yet. "
            "Please contact your academy."
        )

    return profile


# --- Shared lookups ----------------------------------------------------------


def _trainer_summaries(db: Session, trainer_ids) -> dict:
    trainer_ids = {tid for tid in trainer_ids if tid is not None}

    if not trainer_ids:
        return {}

    rows = db.execute(
        select(TrainerProfile, User.full_name, User.avatar_url)
        .join(User, User.id == TrainerProfile.user_id)
        .where(TrainerProfile.id.in_(trainer_ids))
    ).all()

    return {
        trainer.id: {
            "id": trainer.id,
            "full_name": full_name,
            "avatar_url": avatar_url,
            "specialization": trainer.specialization,
            "bio": trainer.bio,
            "experience_years": trainer.experience_years,
        }
        for trainer, full_name, avatar_url in rows
    }


def _themes_for(db: Session, puzzle_ids) -> dict:
    puzzle_ids = set(puzzle_ids)
    themes = {pid: [] for pid in puzzle_ids}

    if not puzzle_ids:
        return themes

    rows = db.execute(
        select(PuzzleThemeMapping.puzzle_id, PuzzleTheme.name)
        .join(PuzzleTheme, PuzzleTheme.id == PuzzleThemeMapping.theme_id)
        .where(PuzzleThemeMapping.puzzle_id.in_(puzzle_ids))
        .order_by(PuzzleTheme.name)
    ).all()

    for puzzle_id, name in rows:
        themes[puzzle_id].append(name)

    return themes


def _group_ids_query(student_id: uuid.UUID):
    return select(GroupMember.group_id).where(GroupMember.student_id == student_id)


def _memberships(db: Session, student_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Group.id, Group.name, User.full_name)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .join(TrainerProfile, TrainerProfile.id == Group.trainer_id)
        .join(User, User.id == TrainerProfile.user_id)
        .where(GroupMember.student_id == student_id)
        .order_by(Group.name)
    ).all()

    return [
        {"id": gid, "name": name, "trainer_name": trainer_name}
        for gid, name, trainer_name in rows
    ]


# --- Assignments -------------------------------------------------------------


def derive_assignment_status(progress: dict, due_date, now: datetime) -> str:
    """Student-facing status, derived only from stored attempts.

    completed   every assignment puzzle has a solved attempt in it
    overdue     not completed and the due date has passed
    in_progress at least one attempt, not completed, not overdue
    pending     no attempts yet
    """
    total = progress["total_puzzles"]

    if total and progress["completed_puzzles"] >= total:
        return "completed"

    if due_date is not None and due_date < now:
        return "overdue"

    if progress["attempts"]:
        return "in_progress"

    return "pending"


def _assignment_rows_query(student_id: uuid.UUID, now: datetime):
    return (
        select(Assignment, Group.name, User.full_name)
        .join(
            AssignmentRecipient,
            and_(
                AssignmentRecipient.assignment_id == Assignment.id,
                AssignmentRecipient.student_id == student_id,
            ),
        )
        .join(TrainerProfile, TrainerProfile.id == Assignment.trainer_id)
        .join(User, User.id == TrainerProfile.user_id)
        .outerjoin(Group, Group.id == Assignment.group_id)
        .where(
            Assignment.status.in_(VISIBLE_ASSIGNMENT_STATUSES),
            or_(Assignment.start_date.is_(None), Assignment.start_date <= now),
        )
    )


def _progress_map(db: Session, student_id: uuid.UUID, assignment_ids) -> dict:
    """Progress per assignment from three grouped queries (no N+1)."""
    assignment_ids = list(set(assignment_ids))
    result = {
        aid: {
            "total_puzzles": 0,
            "completed_puzzles": 0,
            "remaining_puzzles": 0,
            "completion_percent": 0.0,
            "total_points": 0,
            "earned_points": 0,
            "attempts": 0,
            "last_attempt_at": None,
        }
        for aid in assignment_ids
    }

    if not assignment_ids:
        return result

    for aid, count, points in db.execute(
        select(
            AssignmentPuzzle.assignment_id,
            func.count(AssignmentPuzzle.id),
            func.coalesce(func.sum(AssignmentPuzzle.points), 0),
        )
        .where(AssignmentPuzzle.assignment_id.in_(assignment_ids))
        .group_by(AssignmentPuzzle.assignment_id)
    ):
        result[aid]["total_puzzles"] = count
        result[aid]["total_points"] = int(points)

    solved_in_assignment = exists().where(
        PuzzleAttempt.student_id == student_id,
        PuzzleAttempt.assignment_id == AssignmentPuzzle.assignment_id,
        PuzzleAttempt.puzzle_id == AssignmentPuzzle.puzzle_id,
        PuzzleAttempt.is_solved.is_(True),
    )

    for aid, count, points in db.execute(
        select(
            AssignmentPuzzle.assignment_id,
            func.count(AssignmentPuzzle.id),
            func.coalesce(func.sum(AssignmentPuzzle.points), 0),
        )
        .where(
            AssignmentPuzzle.assignment_id.in_(assignment_ids),
            solved_in_assignment,
        )
        .group_by(AssignmentPuzzle.assignment_id)
    ):
        result[aid]["completed_puzzles"] = count
        result[aid]["earned_points"] = int(points)

    for aid, count, last in db.execute(
        select(
            PuzzleAttempt.assignment_id,
            func.count(PuzzleAttempt.id),
            func.max(PuzzleAttempt.attempted_at),
        )
        .where(
            PuzzleAttempt.student_id == student_id,
            PuzzleAttempt.assignment_id.in_(assignment_ids),
        )
        .group_by(PuzzleAttempt.assignment_id)
    ):
        result[aid]["attempts"] = count
        result[aid]["last_attempt_at"] = last

    for progress in result.values():
        total = progress["total_puzzles"]
        progress["remaining_puzzles"] = total - progress["completed_puzzles"]
        progress["completion_percent"] = _percent(
            progress["completed_puzzles"], total
        ) or 0.0

    return result


def _submission_map(db: Session, student_id: uuid.UUID, assignment_ids) -> dict:
    submissions = {}

    if not assignment_ids:
        return submissions

    for submission in db.scalars(
        select(Submission)
        .where(
            Submission.student_id == student_id,
            Submission.assignment_id.in_(list(assignment_ids)),
        )
        .order_by(Submission.attempt_number)
    ):
        # Ordered by attempt number, so the latest submission wins.
        submissions[submission.assignment_id] = {
            "attempt_number": submission.attempt_number,
            "status": submission.status,
            "score": submission.score,
            "submitted_at": submission.submitted_at,
            "trainer_feedback": submission.trainer_feedback,
        }

    return submissions


def _assignment_summaries(db: Session, student_id: uuid.UUID, rows, now) -> list:
    ids = [assignment.id for assignment, _, _ in rows]
    progress = _progress_map(db, student_id, ids)
    submissions = _submission_map(db, student_id, ids)

    summaries = []

    for assignment, group_name, trainer_name in rows:
        assignment_progress = progress[assignment.id]
        summaries.append(
            {
                "id": assignment.id,
                "title": assignment.title,
                "assignment_type": assignment.assignment_type,
                "status": derive_assignment_status(
                    assignment_progress, assignment.due_date, now
                ),
                "is_closed": assignment.status == "completed",
                "due_date": assignment.due_date,
                "published_at": assignment.published_at,
                "group_id": assignment.group_id,
                "group_name": group_name,
                "trainer_name": trainer_name,
                "progress": assignment_progress,
                "submission": submissions.get(assignment.id),
                "description": assignment.description,
            }
        )

    return summaries


def _all_assignment_summaries(
    db: Session, student_id: uuid.UUID, now: datetime, group_id=None
) -> list:
    query = _assignment_rows_query(student_id, now)

    if group_id is not None:
        query = query.where(Assignment.group_id == group_id)

    rows = db.execute(
        query.order_by(
            Assignment.due_date.asc().nulls_last(),
            Assignment.created_at.desc(),
        )
    ).all()

    return _assignment_summaries(db, student_id, rows, now)


def list_assignments(
    db: Session,
    student: StudentProfile,
    params: PageParams,
    status: str | None = None,
) -> dict:
    # The status is derived from attempts, so filtering happens after the
    # grouped progress queries. A student's assignment list is small.
    summaries = _all_assignment_summaries(db, student.id, _now())

    if status is not None:
        summaries = [item for item in summaries if item["status"] == status]

    return paginate_list(summaries, params)


def _get_visible_assignment(
    db: Session, student_id: uuid.UUID, assignment_id: uuid.UUID, now=None
):
    row = db.execute(
        _assignment_rows_query(student_id, now or _now()).where(
            Assignment.id == assignment_id
        )
    ).first()

    if row is None:
        raise NotFoundError("Assignment not found.")

    return row


def _puzzle_attempt_stats(db, student_id, assignment_id) -> dict:
    stats = {}

    for puzzle_id, attempts, solved, solved_at, best_time in db.execute(
        select(
            PuzzleAttempt.puzzle_id,
            func.count(PuzzleAttempt.id),
            func.bool_or(PuzzleAttempt.is_solved),
            func.min(
                case((PuzzleAttempt.is_solved, PuzzleAttempt.attempted_at))
            ),
            func.min(
                case((PuzzleAttempt.is_solved, PuzzleAttempt.time_taken_seconds))
            ),
        )
        .where(
            PuzzleAttempt.student_id == student_id,
            PuzzleAttempt.assignment_id == assignment_id,
        )
        .group_by(PuzzleAttempt.puzzle_id)
    ):
        stats[puzzle_id] = {
            "attempts": attempts,
            "solved": bool(solved),
            "solved_at": solved_at,
            "best_time_seconds": best_time,
        }

    return stats


def _puzzle_status(stat: dict | None) -> str:
    if stat is None:
        return "not_started"
    return "solved" if stat["solved"] else "attempted"


def _assignment_puzzle_rows(db: Session, assignment_id: uuid.UUID):
    return db.execute(
        select(AssignmentPuzzle, Puzzle)
        .join(Puzzle, Puzzle.id == AssignmentPuzzle.puzzle_id)
        .where(AssignmentPuzzle.assignment_id == assignment_id)
        .order_by(AssignmentPuzzle.display_order, AssignmentPuzzle.created_at)
    ).all()


def get_assignment(db: Session, student: StudentProfile, assignment_id) -> dict:
    now = _now()
    row = _get_visible_assignment(db, student.id, assignment_id, now)
    summary = _assignment_summaries(db, student.id, [row], now)[0]

    puzzle_rows = _assignment_puzzle_rows(db, assignment_id)
    themes = _themes_for(db, [puzzle.id for _, puzzle in puzzle_rows])
    stats = _puzzle_attempt_stats(db, student.id, assignment_id)

    summary["puzzles"] = [
        {
            "puzzle_id": puzzle.id,
            "display_order": link.display_order,
            "points": link.points,
            "rating": puzzle.rating,
            "difficulty": puzzle.difficulty,
            "themes": themes[puzzle.id],
            "status": _puzzle_status(stats.get(puzzle.id)),
            "attempts": stats.get(puzzle.id, {}).get("attempts", 0),
            "solved_at": stats.get(puzzle.id, {}).get("solved_at"),
            "best_time_seconds": stats.get(puzzle.id, {}).get("best_time_seconds"),
        }
        for link, puzzle in puzzle_rows
    ]

    return summary


def get_assignment_progress(db: Session, student: StudentProfile, assignment_id):
    row = _get_visible_assignment(db, student.id, assignment_id)
    return _progress_map(db, student.id, [row[0].id])[row[0].id]


def list_assignment_puzzles(db: Session, student: StudentProfile, assignment_id):
    return get_assignment(db, student, assignment_id)["puzzles"]


def submit_assignment(db: Session, student: StudentProfile, assignment_id) -> dict:
    """Hand in an assignment, finished or not.

    Finishing every puzzle submits automatically; this lets a student hand in
    partial work, or resubmit after the trainer returned it. The score is the
    points earned so far, computed on the server.
    """
    assignment, _, _ = _get_visible_assignment(db, student.id, assignment_id)

    if assignment.status == "completed":
        raise ConflictError("This assignment is closed.")

    progress = _progress_map(db, student.id, [assignment.id])[assignment.id]

    if not progress["attempts"]:
        raise ValidationError("Attempt at least one puzzle before submitting.")

    latest = db.scalar(
        select(Submission)
        .where(Submission.assignment_id == assignment.id, Submission.student_id == student.id)
        .order_by(Submission.attempt_number.desc())
        .limit(1)
    )

    if latest is not None and latest.status != "returned":
        raise ConflictError("You have already submitted this assignment.")

    db.add(
        Submission(
            assignment_id=assignment.id,
            student_id=student.id,
            attempt_number=(latest.attempt_number + 1) if latest else 1,
            score=progress["earned_points"],
            status="submitted",
            submitted_at=_now(),
        )
    )
    notification_service.notify_assignment_completed(db, assignment, student)
    db.commit()

    return get_assignment(db, student, assignment.id)


# --- Puzzles -----------------------------------------------------------------


def _load_assignment_puzzle(db, student_id, puzzle_id, assignment_id):
    assignment, _, _ = _get_visible_assignment(db, student_id, assignment_id)
    puzzle_rows = _assignment_puzzle_rows(db, assignment.id)
    ordered_ids = [puzzle.id for _, puzzle in puzzle_rows]

    if puzzle_id not in ordered_ids:
        raise NotFoundError("Puzzle not found.")

    index = ordered_ids.index(puzzle_id)
    link, puzzle = puzzle_rows[index]
    return assignment, link, puzzle, ordered_ids, index


def _parse_puzzle(puzzle: Puzzle):
    try:
        return puzzle_solver.load_puzzle(puzzle.fen, puzzle.solution)
    except puzzle_solver.InvalidPuzzleError as exc:
        raise ValidationError(
            f"This puzzle cannot be played: {exc} Please tell your trainer."
        ) from exc


def get_puzzle(db: Session, student: StudentProfile, puzzle_id, assignment_id):
    assignment, link, puzzle, ordered_ids, index = _load_assignment_puzzle(
        db, student.id, puzzle_id, assignment_id
    )
    board, line = _parse_puzzle(puzzle)

    stat = _puzzle_attempt_stats(db, student.id, assignment.id).get(puzzle.id)
    solved = bool(stat and stat["solved"])
    category = (
        db.scalar(select(PuzzleCategory.name).where(PuzzleCategory.id == puzzle.category_id))
        if puzzle.category_id
        else None
    )

    return {
        "id": puzzle.id,
        "assignment_id": assignment.id,
        "assignment_title": assignment.title,
        "assignment_closed": assignment.status == "completed",
        "display_order": link.display_order,
        "total_in_assignment": len(ordered_ids),
        "previous_puzzle_id": ordered_ids[index - 1] if index > 0 else None,
        "next_puzzle_id": (
            ordered_ids[index + 1] if index + 1 < len(ordered_ids) else None
        ),
        "rating": puzzle.rating,
        "difficulty": puzzle.difficulty,
        "category": category,
        "themes": _themes_for(db, [puzzle.id])[puzzle.id],
        "orientation": "white" if board.turn else "black",
        "moves_required": puzzle_solver.student_moves_required(line),
        "position": puzzle_solver.position_state(board),
        "status": _puzzle_status(stat),
        "attempts": stat["attempts"] if stat else 0,
        "solution_san": (
            puzzle_solver.solution_san(puzzle.fen, puzzle.solution) if solved else None
        ),
        "explanation": puzzle.explanation if solved else None,
    }


def get_hint(
    db: Session,
    student: StudentProfile,
    puzzle_id: uuid.UUID,
    assignment_id: uuid.UUID,
    moves: list[str],
    level: int,
) -> dict:
    """Hint at the next move of an unfinished attempt.

    Nothing is stored: the client reports the hints it used with the finished
    attempt, so the trainer can see them alongside the result.
    """
    assignment, _, puzzle, _, _ = _load_assignment_puzzle(
        db, student.id, puzzle_id, assignment_id
    )

    if assignment.status == "completed":
        raise ConflictError("This assignment is closed and no longer accepts attempts.")

    _parse_puzzle(puzzle)

    try:
        return puzzle_solver.hint(puzzle.fen, puzzle.solution, moves, level)
    except puzzle_solver.IllegalMoveError as exc:
        raise ValidationError(str(exc)) from exc


def _lock_progress(db: Session, student_id: uuid.UUID) -> StudentProgress:
    """Lock the student's progress row so XP and badges are awarded once.

    Concurrent attempts by the same student serialize on this row lock.
    """
    progress = db.scalar(
        select(StudentProgress)
        .where(StudentProgress.student_id == student_id)
        .with_for_update()
    )

    if progress is None:
        progress = StudentProgress(
            student_id=student_id,
            total_xp=0,
            current_streak=0,
            longest_streak=0,
            puzzles_solved=0,
            games_played=0,
        )
        db.add(progress)
        db.flush()

    return progress


def _record_daily_activity(db, student_id, day, solved: bool, xp: int):
    table = DailyActivity.__table__
    statement = pg_insert(DailyActivity).values(
        id=uuid.uuid4(),
        student_id=student_id,
        activity_date=day,
        puzzles_attempted=1,
        puzzles_solved=int(solved),
        games_played=0,
        xp_earned=xp,
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[table.c.student_id, table.c.activity_date],
            set_={
                "puzzles_attempted": table.c.puzzles_attempted + 1,
                "puzzles_solved": table.c.puzzles_solved + int(solved),
                "xp_earned": table.c.xp_earned + xp,
                "updated_at": func.now(),
            },
        )
    )


def _update_streak(db: Session, progress: StudentProgress):
    dates = db.scalars(
        select(DailyActivity.activity_date).where(
            DailyActivity.student_id == progress.student_id
        )
    ).all()
    current, longest = calculate_streaks(dates)
    progress.current_streak = current
    progress.longest_streak = max(progress.longest_streak, longest)


def submit_attempt(
    db: Session,
    student: StudentProfile,
    puzzle_id: uuid.UUID,
    assignment_id: uuid.UUID,
    moves: list[str],
    time_taken_seconds: int | None,
    hints_used: int = 0,
) -> dict:
    """Validate the student's moves on the server and record finished attempts.

    A correct prefix returns ``in_progress`` with the opponent's reply and is
    not stored. A wrong move (``failed``) or a complete line (``solved``)
    stores one ``PuzzleAttempt`` with the moves played. XP is granted only on
    the first solve of a puzzle, plus ``ASSIGNMENT_COMPLETED_XP`` when the
    attempt completes the assignment; badges, daily activity, streaks and the
    assignment submission are updated in the same transaction.
    """
    assignment, link, puzzle, _, _ = _load_assignment_puzzle(
        db, student.id, puzzle_id, assignment_id
    )

    if assignment.status == "completed":
        raise ConflictError("This assignment is closed and no longer accepts attempts.")

    _parse_puzzle(puzzle)

    try:
        result = puzzle_solver.check_line(puzzle.fen, puzzle.solution, moves)
    except puzzle_solver.IllegalMoveError as exc:
        raise ValidationError(str(exc)) from exc

    response = {
        "status": result.status,
        "recorded": False,
        "attempt_id": None,
        "played": [vars(move) for move in result.played],
        "position": puzzle_solver.position_state(result.board),
        "already_solved": False,
        "xp_awarded": 0,
        "badges_awarded": [],
        "solution_san": None,
        "explanation": None,
        "assignment_completed_now": False,
    }

    if result.status == puzzle_solver.STATUS_IN_PROGRESS:
        progress = _progress_map(db, student.id, [assignment.id])[assignment.id]
        response["assignment_progress"] = progress
        response["assignment_status"] = derive_assignment_status(
            progress, assignment.due_date, _now()
        )
        return response

    solved = result.status == puzzle_solver.STATUS_SOLVED
    now = _now()

    student_progress = _lock_progress(db, student.id)

    already_solved = bool(
        db.scalar(
            select(
                exists().where(
                    PuzzleAttempt.student_id == student.id,
                    PuzzleAttempt.puzzle_id == puzzle.id,
                    PuzzleAttempt.is_solved.is_(True),
                )
            )
        )
    )
    before = _progress_map(db, student.id, [assignment.id])[assignment.id]
    was_complete = before["total_puzzles"] and (
        before["completed_puzzles"] >= before["total_puzzles"]
    )

    attempt = PuzzleAttempt(
        student_id=student.id,
        puzzle_id=puzzle.id,
        assignment_id=assignment.id,
        is_solved=solved,
        time_taken_seconds=time_taken_seconds,
        moves=list(moves),
        hints_used=hints_used,
        attempted_at=now,
    )
    db.add(attempt)
    db.flush()

    xp = 0
    badges_awarded = []

    if solved and not already_solved:
        student_progress.puzzles_solved += 1

        if add_xp_event(
            db, student.id, PUZZLE_SOLVED_XP, "Solved a puzzle",
            "puzzle_attempt", attempt.id, now,
        ):
            xp += PUZZLE_SOLVED_XP

        db.flush()

    after = _progress_map(db, student.id, [assignment.id])[assignment.id]
    is_complete = after["total_puzzles"] and (
        after["completed_puzzles"] >= after["total_puzzles"]
    )
    completed_now = bool(is_complete and not was_complete)

    if completed_now:
        has_submission = db.scalar(
            select(
                exists().where(
                    Submission.assignment_id == assignment.id,
                    Submission.student_id == student.id,
                )
            )
        )

        if not has_submission:
            db.add(
                Submission(
                    assignment_id=assignment.id,
                    student_id=student.id,
                    attempt_number=1,
                    score=after["earned_points"],
                    status="submitted",
                    submitted_at=now,
                )
            )

        if add_xp_event(
            db, student.id, ASSIGNMENT_COMPLETED_XP,
            f"Completed assignment {assignment.title}",
            "assignment", assignment.id, now,
        ):
            xp += ASSIGNMENT_COMPLETED_XP

        db.flush()

    if solved and (not already_solved or completed_now):
        for badge, event in award_earned_badges(db, student_progress, now):
            if event is not None:
                xp += event.points
            badges_awarded.append(
                {"code": badge.code, "name": badge.name, "xp_reward": badge.xp_reward}
            )

    student_progress.total_xp += xp
    _record_daily_activity(db, student.id, now.date(), solved, xp)
    db.flush()
    _update_streak(db, student_progress)
    streak = (student_progress.current_streak, student_progress.longest_streak)

    if completed_now:
        notification_service.notify_assignment_completed(db, assignment, student)

    db.commit()
    streak_cache.store(student.id, streak[0], streak[1], now.date())

    response.update(
        recorded=True,
        attempt_id=attempt.id,
        already_solved=already_solved,
        xp_awarded=xp,
        badges_awarded=badges_awarded,
        assignment_progress=after,
        assignment_status=derive_assignment_status(after, assignment.due_date, now),
        assignment_completed_now=completed_now,
    )

    if solved:
        response["solution_san"] = puzzle_solver.solution_san(
            puzzle.fen, puzzle.solution
        )
        response["explanation"] = puzzle.explanation

    return response


# --- Sessions and attendance -------------------------------------------------


def _session_is_upcoming(session: ClassSession, now: datetime) -> bool:
    return session.status in UPCOMING_SESSION_STATUSES and session.end_time >= now


def _visible_sessions_query(student_id: uuid.UUID):
    own = aliased(SessionAttendance)

    query = (
        select(ClassSession, Group.name, User.full_name, own.status, own.remarks)
        .join(TrainerProfile, TrainerProfile.id == ClassSession.trainer_id)
        .join(User, User.id == TrainerProfile.user_id)
        .outerjoin(Group, Group.id == ClassSession.group_id)
        .outerjoin(
            own,
            and_(own.session_id == ClassSession.id, own.student_id == student_id),
        )
        .where(
            or_(
                and_(
                    ClassSession.session_type == "group",
                    ClassSession.group_id.in_(_group_ids_query(student_id)),
                ),
                own.id.is_not(None),
            )
        )
    )
    return query


def _session_item(row, now: datetime, detail: bool = False) -> dict:
    session, group_name, trainer_name, attendance_status, remarks = row
    item = {
        "id": session.id,
        "title": session.title,
        "session_type": session.session_type,
        "status": session.status,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "group_id": session.group_id,
        "group_name": group_name,
        "trainer_name": trainer_name,
        "attendance_status": attendance_status,
        "is_upcoming": _session_is_upcoming(session, now),
    }

    if detail:
        item.update(
            description=session.description,
            meeting_url=session.meeting_url,
            attendance_remarks=remarks,
        )

    return item


def _scoped_sessions(student_id, scope: str, now: datetime, group_id=None):
    query = _visible_sessions_query(student_id)
    upcoming = and_(
        ClassSession.status.in_(UPCOMING_SESSION_STATUSES),
        ClassSession.end_time >= now,
    )

    if group_id is not None:
        query = query.where(ClassSession.group_id == group_id)

    if scope == "upcoming":
        return query.where(upcoming).order_by(ClassSession.start_time.asc())

    if scope == "past":
        query = query.where(~upcoming)

    return query.order_by(ClassSession.start_time.desc())


def list_sessions(db: Session, student: StudentProfile, params: PageParams, scope="all"):
    now = _now()
    query = _scoped_sessions(student.id, scope, now)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = db.execute(query.limit(params.page_size).offset(params.offset)).all()
    return make_page([_session_item(row, now) for row in rows], total or 0, params)


def get_session(db: Session, student: StudentProfile, session_id) -> dict:
    row = db.execute(
        _visible_sessions_query(student.id).where(ClassSession.id == session_id)
    ).first()

    if row is None:
        raise NotFoundError("Session not found.")

    return _session_item(row, _now(), detail=True)


def list_attendance(db: Session, student: StudentProfile, params: PageParams) -> dict:
    base = (
        select(SessionAttendance, ClassSession, User.full_name, Group.name)
        .join(ClassSession, ClassSession.id == SessionAttendance.session_id)
        .join(TrainerProfile, TrainerProfile.id == ClassSession.trainer_id)
        .join(User, User.id == TrainerProfile.user_id)
        .outerjoin(Group, Group.id == ClassSession.group_id)
        .where(SessionAttendance.student_id == student.id)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(ClassSession.start_time.desc())
        .limit(params.page_size)
        .offset(params.offset)
    ).all()

    counts = dict(
        db.execute(
            select(SessionAttendance.status, func.count())
            .where(SessionAttendance.student_id == student.id)
            .group_by(SessionAttendance.status)
        ).all()
    )
    attended = counts.get("present", 0) + counts.get("late", 0)

    page = make_page(
        [
            {
                "session_id": session.id,
                "session_title": session.title,
                "session_status": session.status,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "trainer_name": trainer_name,
                "group_name": group_name,
                "status": attendance.status,
                "remarks": attendance.remarks,
            }
            for attendance, session, trainer_name, group_name in rows
        ],
        total,
        params,
    )
    page["summary"] = {
        "total": sum(counts.values()),
        "present": counts.get("present", 0),
        "late": counts.get("late", 0),
        "absent": counts.get("absent", 0),
        "excused": counts.get("excused", 0),
        "scheduled": counts.get("scheduled", 0),
        # Excused and not-yet-recorded sessions do not count either way.
        "attendance_rate_percent": _percent(
            attended, attended + counts.get("absent", 0)
        ),
    }
    return page


# --- Groups ------------------------------------------------------------------


def _group_summaries(db: Session, student_id: uuid.UUID, group_id=None) -> list:
    query = (
        select(Group, GroupMember.created_at)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.student_id == student_id)
        .order_by(Group.name)
    )

    if group_id is not None:
        query = query.where(Group.id == group_id)

    rows = db.execute(query).all()
    ids = [group.id for group, _ in rows]

    if not ids:
        return []

    now = _now()
    member_counts = dict(
        db.execute(
            select(GroupMember.group_id, func.count())
            .where(GroupMember.group_id.in_(ids))
            .group_by(GroupMember.group_id)
        ).all()
    )
    upcoming_counts = dict(
        db.execute(
            select(ClassSession.group_id, func.count())
            .where(
                ClassSession.group_id.in_(ids),
                ClassSession.status.in_(UPCOMING_SESSION_STATUSES),
                ClassSession.end_time >= now,
                or_(
                    ClassSession.session_type == "group",
                    exists().where(
                        SessionAttendance.session_id == ClassSession.id,
                        SessionAttendance.student_id == student_id,
                    ),
                ),
            )
            .group_by(ClassSession.group_id)
        ).all()
    )
    trainers = _trainer_summaries(db, [group.trainer_id for group, _ in rows])

    return [
        {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "is_active": group.is_active,
            "trainer": trainers[group.trainer_id],
            "member_count": member_counts.get(group.id, 0),
            "joined_at": joined_at,
            "upcoming_session_count": upcoming_counts.get(group.id, 0),
        }
        for group, joined_at in rows
    ]


def list_groups(db: Session, student: StudentProfile, params: PageParams) -> dict:
    return paginate_list(_group_summaries(db, student.id), params)


def get_group(db: Session, student: StudentProfile, group_id) -> dict:
    groups = _group_summaries(db, student.id, group_id)

    if not groups:
        raise NotFoundError("Group not found.")

    group = groups[0]
    now = _now()

    upcoming = db.execute(
        _scoped_sessions(student.id, "upcoming", now, group_id).limit(5)
    ).all()
    recent = db.execute(
        _scoped_sessions(student.id, "past", now, group_id).limit(5)
    ).all()

    group["upcoming_sessions"] = [_session_item(row, now) for row in upcoming]
    group["recent_sessions"] = [_session_item(row, now) for row in recent]
    group["assignments"] = _all_assignment_summaries(db, student.id, now, group_id)
    return group


# --- Profile -----------------------------------------------------------------


def get_profile(db: Session, user: User) -> dict:
    profile = find_student_profile(db, user)
    trainer = None
    student = None
    groups = []

    if profile is not None:
        trainer = _trainer_summaries(db, [profile.trainer_id]).get(profile.trainer_id)
        student = {
            "date_of_birth": profile.date_of_birth,
            "chess_rating": profile.chess_rating,
            "level": profile.level,
            "joined_at": profile.created_at,
        }
        groups = _memberships(db, profile.id)

    return {"account": user, "student": student, "trainer": trainer, "groups": groups}


USER_EDITABLE_FIELDS = ("full_name", "phone", "avatar_url", "language")


def update_profile(db: Session, user: User, changes: dict) -> dict:
    """Apply only whitelisted fields; role, status and email are not editable."""
    if "full_name" in changes and changes["full_name"] is None:
        raise ValidationError("Full name cannot be empty.")

    if "language" in changes and changes["language"] is None:
        raise ValidationError("Language cannot be empty.")

    for field in USER_EDITABLE_FIELDS:
        if field in changes:
            setattr(user, field, changes[field])

    if "date_of_birth" in changes:
        profile = find_student_profile(db, user)

        if profile is None:
            raise ConflictError(
                "Your student profile has not been set up yet, so a date "
                "of birth cannot be saved."
            )

        profile.date_of_birth = changes["date_of_birth"]

    db.commit()
    db.refresh(user)
    return get_profile(db, user)


# --- Gamification ------------------------------------------------------------


def _progress_values(db: Session, student_id: uuid.UUID) -> dict:
    progress = db.scalar(
        select(StudentProgress).where(StudentProgress.student_id == student_id)
    )
    values = {
        "total_xp": progress.total_xp if progress else 0,
        "puzzles_solved": progress.puzzles_solved if progress else 0,
        "games_played": progress.games_played if progress else 0,
        "assignments_completed": (
            badge_counters(db, progress)["assignments_completed"] if progress else 0
        ),
    }

    cached = streak_cache.load(student_id, today_utc())

    if cached is not None:
        cached["longest_streak"] = max(
            progress.longest_streak if progress else 0, cached["longest_streak"]
        )
        return {**values, **cached}

    dates = db.scalars(
        select(DailyActivity.activity_date).where(DailyActivity.student_id == student_id)
    ).all()
    _, longest = calculate_streaks(dates)

    return {
        **values,
        "current_streak": active_streak(dates, today_utc()),
        "longest_streak": max(progress.longest_streak if progress else 0, longest),
        "last_activity_date": max(dates) if dates else None,
    }


# Days shown in the consistency calendar on the achievements page.
ACTIVITY_CALENDAR_DAYS = 112


def activity_calendar(db: Session, student_id: uuid.UUID, days: int = ACTIVITY_CALENDAR_DAYS) -> list:
    """One entry per UTC day (oldest first) with that day's recorded activity."""
    end = today_utc()
    start = end - timedelta(days=days - 1)
    rows = {
        row.activity_date: row
        for row in db.scalars(
            select(DailyActivity).where(
                DailyActivity.student_id == student_id,
                DailyActivity.activity_date >= start,
                DailyActivity.activity_date <= end,
            )
        )
    }
    calendar = []

    for offset in range(days):
        day = start + timedelta(days=offset)
        row = rows.get(day)
        calendar.append(
            {
                "date": day,
                "puzzles_attempted": row.puzzles_attempted if row else 0,
                "puzzles_solved": row.puzzles_solved if row else 0,
                "xp_earned": row.xp_earned if row else 0,
            }
        )

    return calendar


def _badge_collection(db: Session, student_id: uuid.UUID) -> list:
    earned = dict(
        db.execute(
            select(StudentBadge.badge_id, StudentBadge.earned_at).where(
                StudentBadge.student_id == student_id
            )
        ).all()
    )
    badges = db.scalars(select(Badge).order_by(Badge.xp_reward, Badge.name)).all()

    return [
        {
            "id": badge.id,
            "code": badge.code,
            "name": badge.name,
            "description": badge.description,
            "icon_url": badge.icon_url,
            "xp_reward": badge.xp_reward,
            "earned": badge.id in earned,
            "earned_at": earned.get(badge.id),
        }
        for badge in badges
    ], badges


def list_badges(db: Session, student: StudentProfile) -> list:
    return _badge_collection(db, student.id)[0]


def get_gamification(db: Session, student: StudentProfile) -> dict:
    values = _progress_values(db, student.id)
    collection, badges = _badge_collection(db, student.id)
    earned = [item for item in collection if item["earned"]]
    recent_xp = db.scalars(
        select(XPEvent)
        .where(XPEvent.student_id == student.id)
        .order_by(XPEvent.created_at.desc())
        .limit(10)
    ).all()

    calendar = activity_calendar(db, student.id)

    return {
        **values,
        "level": student.level,
        "xp_level": level_for_xp(values["total_xp"]),
        "activity_calendar": calendar,
        "active_days": sum(1 for day in calendar if day["puzzles_attempted"]),
        "badges_earned": len(earned),
        "badges_total": len(collection),
        "recent_badges": sorted(earned, key=lambda b: b["earned_at"], reverse=True)[:5],
        "recent_xp": [
            {
                "id": event.id,
                "points": event.points,
                "reason": event.reason,
                "source_type": event.source_type,
                "created_at": event.created_at,
            }
            for event in recent_xp
        ],
        "next_milestone": next_milestone(
            values, {item["code"] for item in earned}, badges
        ),
    }


# --- Progress and activity ---------------------------------------------------


def _attempt_items(db: Session, rows) -> list:
    themes = _themes_for(db, [attempt.puzzle_id for attempt, _, _ in rows])
    return [
        {
            "id": attempt.id,
            "puzzle_id": attempt.puzzle_id,
            "assignment_id": attempt.assignment_id,
            "assignment_title": assignment_title,
            "is_solved": attempt.is_solved,
            "time_taken_seconds": attempt.time_taken_seconds,
            "attempted_at": attempt.attempted_at,
            "rating": puzzle.rating,
            "difficulty": puzzle.difficulty,
            "themes": themes[attempt.puzzle_id],
        }
        for attempt, puzzle, assignment_title in rows
    ]


def _attempts_query(student_id: uuid.UUID):
    return (
        select(PuzzleAttempt, Puzzle, Assignment.title)
        .join(Puzzle, Puzzle.id == PuzzleAttempt.puzzle_id)
        .outerjoin(Assignment, Assignment.id == PuzzleAttempt.assignment_id)
        .where(PuzzleAttempt.student_id == student_id)
        .order_by(PuzzleAttempt.attempted_at.desc())
    )


def list_activity(db: Session, student: StudentProfile, params: PageParams) -> dict:
    total = db.scalar(
        select(func.count(PuzzleAttempt.id)).where(PuzzleAttempt.student_id == student.id)
    ) or 0
    rows = db.execute(
        _attempts_query(student.id).limit(params.page_size).offset(params.offset)
    ).all()
    return make_page(_attempt_items(db, rows), total, params)


def _breakdown(db: Session, student_id: uuid.UUID, label_column, joins) -> list:
    solved_puzzle = case((PuzzleAttempt.is_solved, PuzzleAttempt.puzzle_id))
    query = select(
        label_column,
        func.count(PuzzleAttempt.id),
        func.count(case((PuzzleAttempt.is_solved, 1))),
        func.count(distinct(solved_puzzle)),
    ).select_from(PuzzleAttempt)

    for target, condition in joins:
        query = query.join(target, condition)

    rows = db.execute(
        query.where(PuzzleAttempt.student_id == student_id)
        .group_by(label_column)
        .order_by(label_column)
    ).all()

    return [
        {
            "label": label,
            "attempts": attempts,
            "solved_attempts": solved,
            "puzzles_solved": puzzles,
            "accuracy_percent": _percent(solved, attempts) or 0.0,
        }
        for label, attempts, solved, puzzles in rows
    ]


def get_progress(db: Session, student: StudentProfile) -> dict:
    total, solved, attempted_puzzles, solved_puzzles, avg_time = db.execute(
        select(
            func.count(PuzzleAttempt.id),
            func.count(case((PuzzleAttempt.is_solved, 1))),
            func.count(distinct(PuzzleAttempt.puzzle_id)),
            func.count(distinct(case((PuzzleAttempt.is_solved, PuzzleAttempt.puzzle_id)))),
            func.avg(case((PuzzleAttempt.is_solved, PuzzleAttempt.time_taken_seconds))),
        ).where(PuzzleAttempt.student_id == student.id)
    ).one()

    assignments = _all_assignment_summaries(db, student.id, _now())
    completed = sum(1 for item in assignments if item["status"] == "completed")
    values = _progress_values(db, student.id)

    since = today_utc() - timedelta(days=29)
    daily = db.scalars(
        select(DailyActivity)
        .where(
            DailyActivity.student_id == student.id,
            DailyActivity.activity_date >= since,
        )
        .order_by(DailyActivity.activity_date)
    ).all()

    return {
        "puzzles_attempted": attempted_puzzles,
        "puzzles_solved": solved_puzzles,
        "total_attempts": total,
        "solved_attempts": solved,
        "accuracy_percent": _percent(solved, total),
        "average_solve_time_seconds": (
            round(float(avg_time), 1) if avg_time is not None else None
        ),
        "assignments_total": len(assignments),
        "assignments_completed": completed,
        "assignment_completion_percent": _percent(completed, len(assignments)),
        "total_xp": values["total_xp"],
        "current_streak": values["current_streak"],
        "longest_streak": values["longest_streak"],
        "daily": [
            {
                "date": row.activity_date,
                "puzzles_attempted": row.puzzles_attempted,
                "puzzles_solved": row.puzzles_solved,
                "xp_earned": row.xp_earned,
            }
            for row in daily
        ],
        "themes": _breakdown(
            db,
            student.id,
            PuzzleTheme.name,
            [
                (PuzzleThemeMapping, PuzzleThemeMapping.puzzle_id == PuzzleAttempt.puzzle_id),
                (PuzzleTheme, PuzzleTheme.id == PuzzleThemeMapping.theme_id),
            ],
        ),
        "difficulties": _breakdown(
            db,
            student.id,
            func.coalesce(Puzzle.difficulty, "unrated"),
            [(Puzzle, Puzzle.id == PuzzleAttempt.puzzle_id)],
        ),
        "metric_definitions": METRIC_DEFINITIONS,
    }


# --- Dashboard ---------------------------------------------------------------


def get_dashboard(db: Session, user: User, student: StudentProfile) -> dict:
    now = _now()
    assignments = _all_assignment_summaries(db, student.id, now)
    counts = {status: 0 for status in ASSIGNMENT_STATUSES}

    for item in assignments:
        counts[item["status"]] += 1

    active = [item for item in assignments if item["status"] != "completed"]
    completed = sorted(
        (item for item in assignments if item["status"] == "completed"),
        key=lambda item: item["progress"]["last_attempt_at"] or now,
        reverse=True,
    )

    upcoming = db.execute(_scoped_sessions(student.id, "upcoming", now).limit(5)).all()
    recent_attempts = db.execute(_attempts_query(student.id).limit(5)).all()

    total, solved = db.execute(
        select(
            func.count(PuzzleAttempt.id),
            func.count(case((PuzzleAttempt.is_solved, 1))),
        ).where(PuzzleAttempt.student_id == student.id)
    ).one()

    gamification = get_gamification(db, student)

    return {
        "profile": {
            "full_name": user.full_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "level": student.level,
            "chess_rating": student.chess_rating,
        },
        "trainer": _trainer_summaries(db, [student.trainer_id]).get(student.trainer_id),
        "groups": _memberships(db, student.id),
        "assignment_counts": {"total": len(assignments), **counts},
        "active_assignments": active[:5],
        "recently_completed": completed[:3],
        "upcoming_sessions": [_session_item(row, now) for row in upcoming],
        "recent_attempts": _attempt_items(db, recent_attempts),
        "stats": {
            "puzzles_solved": gamification["puzzles_solved"],
            "total_attempts": total,
            "accuracy_percent": _percent(solved, total),
            "total_xp": gamification["total_xp"],
            "current_streak": gamification["current_streak"],
            "longest_streak": gamification["longest_streak"],
            "badges_earned": gamification["badges_earned"],
        },
        "recent_badges": gamification["recent_badges"][:3],
        "next_milestone": gamification["next_milestone"],
    }
