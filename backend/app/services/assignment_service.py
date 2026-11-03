"""Trainer assignment management.

Lifecycle: draft -> published -> completed (closed), and draft/published ->
cancelled. Only drafts can be edited. An assignment targets one of the
trainer's groups, either the whole group (``assignment_type='group'``, the
recipients are re-synced to the current members when it is published) or
selected members (``'individual'``).

Progress counts only puzzle attempts linked to the assignment
(``puzzle_attempts.assignment_id``); a recipient has completed it once every
assignment puzzle has a solved attempt.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.services import notification_service
from app.models import (
    Assignment,
    AssignmentPuzzle,
    AssignmentRecipient,
    Group,
    Puzzle,
    PuzzleAttempt,
    StudentProfile,
    Submission,
    TrainerProfile,
    User,
)
from app.services.stats_service import (
    assignment_attempt_progress,
    assignment_puzzle_totals,
    percent,
)
from app.services.trainer_access import (
    get_active_owned_group,
    get_owned_group,
    group_member_ids,
    like_pattern,
)
from app.utils.pagination import PageParams, make_page, paginate

ASSIGNMENT_SORTS = {
    "-created_at": Assignment.created_at.desc(),
    "created_at": Assignment.created_at.asc(),
    "due_date": Assignment.due_date.asc().nulls_last(),
    "-due_date": Assignment.due_date.desc().nulls_last(),
    "title": Assignment.title.asc(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summary_query(trainer: TrainerProfile):
    totals = assignment_puzzle_totals()
    progress = assignment_attempt_progress()

    recipients = (
        select(AssignmentRecipient.assignment_id, func.count().label("recipient_count"))
        .group_by(AssignmentRecipient.assignment_id)
        .subquery()
    )
    completed = (
        select(AssignmentRecipient.assignment_id, func.count().label("completed_count"))
        .join(totals, totals.c.assignment_id == AssignmentRecipient.assignment_id)
        .join(
            progress,
            and_(
                progress.c.assignment_id == AssignmentRecipient.assignment_id,
                progress.c.student_id == AssignmentRecipient.student_id,
            ),
        )
        .where(totals.c.puzzles_total > 0, progress.c.solved >= totals.c.puzzles_total)
        .group_by(AssignmentRecipient.assignment_id)
        .subquery()
    )

    return (
        select(
            Assignment,
            Group.name.label("group_name"),
            func.coalesce(totals.c.puzzles_total, 0).label("puzzle_count"),
            func.coalesce(recipients.c.recipient_count, 0).label("recipient_count"),
            func.coalesce(completed.c.completed_count, 0).label("completed_count"),
        )
        .outerjoin(Group, Group.id == Assignment.group_id)
        .outerjoin(totals, totals.c.assignment_id == Assignment.id)
        .outerjoin(recipients, recipients.c.assignment_id == Assignment.id)
        .outerjoin(completed, completed.c.assignment_id == Assignment.id)
        .where(Assignment.trainer_id == trainer.id)
    )


def _summary(row) -> dict:
    assignment = row.Assignment
    return {
        "id": assignment.id,
        "title": assignment.title,
        "status": assignment.status,
        "assignment_type": assignment.assignment_type,
        "group": (
            {"id": assignment.group_id, "name": row.group_name}
            if assignment.group_id else None
        ),
        "start_date": assignment.start_date,
        "due_date": assignment.due_date,
        "published_at": assignment.published_at,
        "created_at": assignment.created_at,
        "puzzle_count": row.puzzle_count,
        "recipient_count": row.recipient_count,
        "completed_count": row.completed_count,
    }


def list_assignments(
    db: Session,
    trainer: TrainerProfile,
    params: PageParams,
    *,
    status: str | None = None,
    group_id: uuid.UUID | None = None,
    search: str | None = None,
    sort: str = "-created_at",
) -> dict:
    query = _summary_query(trainer)

    if status:
        query = query.where(Assignment.status == status)
    if group_id:
        get_owned_group(db, trainer, group_id)
        query = query.where(Assignment.group_id == group_id)
    if search and search.strip():
        query = query.where(Assignment.title.ilike(like_pattern(search)))

    query = query.order_by(ASSIGNMENT_SORTS.get(sort, ASSIGNMENT_SORTS["-created_at"]), Assignment.id)
    rows, total = paginate(db, query, params)

    return make_page([_summary(row) for row in rows], total, params)


def recent_assignments(db: Session, trainer: TrainerProfile, limit: int = 5) -> list[dict]:
    rows = db.execute(
        _summary_query(trainer)
        .where(Assignment.status != "cancelled")
        .order_by(Assignment.created_at.desc())
        .limit(limit)
    )
    return [_summary(row) for row in rows]


def _get_owned_assignment(db: Session, trainer: TrainerProfile, assignment_id: uuid.UUID) -> Assignment:
    assignment = db.get(Assignment, assignment_id)

    if assignment is None or assignment.trainer_id != trainer.id:
        raise NotFoundError("Assignment not found.")

    return assignment


def get_assignment(db: Session, trainer: TrainerProfile, assignment_id: uuid.UUID) -> dict:
    row = db.execute(
        _summary_query(trainer).where(Assignment.id == assignment_id)
    ).first()

    if row is None:
        raise NotFoundError("Assignment not found.")

    puzzles = db.execute(
        select(AssignmentPuzzle, Puzzle)
        .join(Puzzle, Puzzle.id == AssignmentPuzzle.puzzle_id)
        .where(AssignmentPuzzle.assignment_id == assignment_id)
        .order_by(AssignmentPuzzle.display_order, AssignmentPuzzle.id)
    ).all()

    recipients = db.execute(
        select(AssignmentRecipient.student_id, User.full_name, User.email)
        .join(StudentProfile, StudentProfile.id == AssignmentRecipient.student_id)
        .join(User, User.id == StudentProfile.user_id)
        .where(AssignmentRecipient.assignment_id == assignment_id)
        .order_by(User.full_name)
    ).all()

    return {
        **_summary(row),
        "description": row.Assignment.description,
        "puzzles": [
            {
                "puzzle_id": puzzle.id,
                "display_order": link.display_order,
                "points": link.points,
                "fen": puzzle.fen,
                "rating": puzzle.rating,
                "difficulty": puzzle.difficulty,
                "status": puzzle.status,
            }
            for link, puzzle in puzzles
        ],
        "recipients": [row._asdict() for row in recipients],
    }


def _check_puzzles(db: Session, trainer: TrainerProfile, puzzle_ids: list[uuid.UUID]) -> None:
    """Puzzles must exist, be visible to the trainer and be published."""
    if not puzzle_ids:
        return

    usable = set(
        db.scalars(
            select(Puzzle.id).where(
                Puzzle.id.in_(puzzle_ids),
                Puzzle.status == "published",
            )
        )
    )

    if usable != set(puzzle_ids):
        raise ValidationError(
            "Every puzzle must exist and be published. "
            "Publish your draft puzzles before assigning them."
        )


def _set_puzzles(db: Session, assignment: Assignment, puzzle_ids: list[uuid.UUID]) -> None:
    db.execute(delete(AssignmentPuzzle).where(AssignmentPuzzle.assignment_id == assignment.id))
    db.flush()

    for order, puzzle_id in enumerate(puzzle_ids, start=1):
        db.add(AssignmentPuzzle(assignment_id=assignment.id, puzzle_id=puzzle_id, display_order=order))


def _set_recipients(db: Session, assignment: Assignment, student_ids: set[uuid.UUID]) -> None:
    """Make the recipient rows exactly ``student_ids`` (no duplicates)."""
    current = set(
        db.scalars(
            select(AssignmentRecipient.student_id)
            .where(AssignmentRecipient.assignment_id == assignment.id)
        )
    )

    stale = current - student_ids
    if stale:
        db.execute(
            delete(AssignmentRecipient).where(
                AssignmentRecipient.assignment_id == assignment.id,
                AssignmentRecipient.student_id.in_(stale),
            )
        )

    for student_id in student_ids - current:
        db.add(AssignmentRecipient(assignment_id=assignment.id, student_id=student_id))


def _resolve_recipients(
    db: Session, group: Group, student_ids: list[uuid.UUID] | None
) -> tuple[str, set[uuid.UUID]]:
    members = group_member_ids(db, group.id)

    if student_ids is None:
        return "group", members

    if not student_ids:
        raise ValidationError("Select at least one student, or assign the whole group.")

    outside = set(student_ids) - members
    if outside:
        raise ValidationError("All selected students must be members of the selected group.")

    return "individual", set(student_ids)


def _check_dates(start_date: datetime | None, due_date: datetime | None) -> None:
    if start_date and due_date and due_date < start_date:
        raise ValidationError("Due date cannot be earlier than the start date.")


def create_assignment(db: Session, trainer: TrainerProfile, data: dict) -> dict:
    group = get_active_owned_group(db, trainer, data["group_id"])
    puzzle_ids = data.get("puzzle_ids") or []
    _check_puzzles(db, trainer, puzzle_ids)
    _check_dates(data.get("start_date"), data.get("due_date"))
    assignment_type, recipients = _resolve_recipients(db, group, data.get("student_ids"))

    assignment = Assignment(
        trainer_id=trainer.id,
        group_id=group.id,
        title=data["title"],
        description=data.get("description"),
        assignment_type=assignment_type,
        status="draft",
        start_date=data.get("start_date"),
        due_date=data.get("due_date"),
    )
    db.add(assignment)
    db.flush()

    _set_puzzles(db, assignment, puzzle_ids)
    _set_recipients(db, assignment, recipients)

    if data.get("publish"):
        db.flush()
        _publish(db, assignment)

    db.commit()
    return get_assignment(db, trainer, assignment.id)


def update_assignment(db: Session, trainer: TrainerProfile, assignment_id: uuid.UUID, changes: dict) -> dict:
    assignment = _get_owned_assignment(db, trainer, assignment_id)

    if assignment.status != "draft":
        raise ConflictError("Only draft assignments can be edited.")

    group_changed = "group_id" in changes and changes["group_id"] != assignment.group_id
    group = get_active_owned_group(db, trainer, changes.get("group_id") or assignment.group_id)

    if changes.get("title"):
        assignment.title = changes["title"].strip()
    if "description" in changes:
        assignment.description = changes["description"]

    start_date = changes["start_date"] if "start_date" in changes else assignment.start_date
    due_date = changes["due_date"] if "due_date" in changes else assignment.due_date
    _check_dates(start_date, due_date)
    assignment.start_date, assignment.due_date = start_date, due_date

    if changes.get("puzzle_ids") is not None:
        _check_puzzles(db, trainer, changes["puzzle_ids"])
        _set_puzzles(db, assignment, changes["puzzle_ids"])

    if "student_ids" in changes or group_changed:
        # Changing the group without new selections targets the whole group.
        student_ids = changes.get("student_ids") if "student_ids" in changes else None
        assignment.assignment_type, recipients = _resolve_recipients(db, group, student_ids)
        _set_recipients(db, assignment, recipients)

    assignment.group_id = group.id

    db.commit()
    return get_assignment(db, trainer, assignment.id)


def _publish(db: Session, assignment: Assignment) -> None:
    group = db.get(Group, assignment.group_id) if assignment.group_id else None

    if group is None or not group.is_active:
        raise ConflictError("The assignment's group is missing or inactive.")

    puzzle_ids = list(
        db.scalars(select(AssignmentPuzzle.puzzle_id).where(AssignmentPuzzle.assignment_id == assignment.id))
    )

    if not puzzle_ids:
        raise ValidationError("Add at least one puzzle before publishing.")

    unpublished = db.scalar(
        select(func.count()).where(Puzzle.id.in_(puzzle_ids), Puzzle.status != "published")
    )
    if unpublished:
        raise ValidationError("All puzzles must be published before the assignment is published.")

    if assignment.due_date and assignment.due_date <= _now():
        raise ValidationError("The due date is in the past.")

    members = group_member_ids(db, group.id)

    if assignment.assignment_type == "group":
        recipients = members
    else:
        recipients = set(
            db.scalars(
                select(AssignmentRecipient.student_id)
                .where(AssignmentRecipient.assignment_id == assignment.id)
            )
        )
        if recipients - members:
            raise ValidationError("Some selected students are no longer members of the group.")

    if not recipients:
        raise ValidationError("The assignment has no recipients; the group has no students.")

    _set_recipients(db, assignment, recipients)
    assignment.status = "published"
    assignment.published_at = _now()
    notification_service.notify_assignment_published(db, assignment, recipients)


ASSIGNMENT_TRANSITIONS = {
    "close": ({"published"}, "completed"),
    "cancel": ({"draft", "published"}, "cancelled"),
}


def change_assignment_status(db: Session, trainer: TrainerProfile, assignment_id: uuid.UUID, action: str) -> dict:
    assignment = _get_owned_assignment(db, trainer, assignment_id)

    if action == "publish":
        if assignment.status != "draft":
            raise ConflictError("Only draft assignments can be published.")
        _publish(db, assignment)
    else:
        allowed, new_status = ASSIGNMENT_TRANSITIONS[action]
        if assignment.status not in allowed:
            raise ConflictError(f"Cannot {action} an assignment that is {assignment.status}.")
        assignment.status = new_status

    db.commit()
    return get_assignment(db, trainer, assignment.id)


def assignment_progress(db: Session, trainer: TrainerProfile, assignment_id: uuid.UUID) -> dict:
    assignment = _get_owned_assignment(db, trainer, assignment_id)

    puzzles_total = db.scalar(
        select(func.count()).where(AssignmentPuzzle.assignment_id == assignment.id)
    ) or 0

    progress = assignment_attempt_progress()
    latest_submission = (
        select(
            Submission.id,
            Submission.student_id,
            Submission.status,
            Submission.score,
            Submission.trainer_feedback,
            func.row_number()
            .over(partition_by=Submission.student_id, order_by=Submission.attempt_number.desc())
            .label("rank"),
        )
        .where(Submission.assignment_id == assignment.id)
        .subquery()
    )

    rows = db.execute(
        select(
            AssignmentRecipient.student_id,
            User.full_name,
            User.email,
            func.coalesce(progress.c.attempted, 0).label("attempted"),
            func.coalesce(progress.c.solved, 0).label("solved"),
            func.coalesce(progress.c.attempts, 0).label("attempts"),
            progress.c.last_attempt_at,
            latest_submission.c.id.label("submission_id"),
            latest_submission.c.status.label("submission_status"),
            latest_submission.c.score.label("submission_score"),
            latest_submission.c.trainer_feedback.label("trainer_feedback"),
        )
        .join(StudentProfile, StudentProfile.id == AssignmentRecipient.student_id)
        .join(User, User.id == StudentProfile.user_id)
        .outerjoin(
            progress,
            and_(
                progress.c.assignment_id == AssignmentRecipient.assignment_id,
                progress.c.student_id == AssignmentRecipient.student_id,
            ),
        )
        .outerjoin(
            latest_submission,
            and_(
                latest_submission.c.student_id == AssignmentRecipient.student_id,
                latest_submission.c.rank == 1,
            ),
        )
        .where(AssignmentRecipient.assignment_id == assignment.id)
        .order_by(User.full_name)
    ).all()

    recipients = []
    for row in rows:
        if puzzles_total and row.solved >= puzzles_total:
            status = "completed"
        elif row.attempts:
            status = "in_progress"
        else:
            status = "not_started"

        recipients.append({
            "student_id": row.student_id,
            "full_name": row.full_name,
            "email": row.email,
            "puzzles_total": puzzles_total,
            "puzzles_attempted": row.attempted,
            "puzzles_solved": row.solved,
            "attempts": row.attempts,
            "completion_percent": percent(row.solved, puzzles_total) or 0.0,
            "status": status,
            "last_activity_at": row.last_attempt_at,
            "submission_id": row.submission_id,
            "submission_status": row.submission_status,
            "submission_score": row.submission_score,
            "trainer_feedback": row.trainer_feedback,
        })

    counts = {key: sum(1 for r in recipients if r["status"] == key)
              for key in ("completed", "in_progress", "not_started")}

    return {
        "assignment_id": assignment.id,
        "title": assignment.title,
        "status": assignment.status,
        "due_date": assignment.due_date,
        "is_overdue": bool(
            assignment.status == "published"
            and assignment.due_date
            and assignment.due_date < _now()
            and counts["completed"] < len(recipients)
        ),
        "puzzles_total": puzzles_total,
        "recipients_total": len(recipients),
        "completed_count": counts["completed"],
        "in_progress_count": counts["in_progress"],
        "not_started_count": counts["not_started"],
        "completion_rate": percent(counts["completed"], len(recipients)),
        "average_completion_percent": (
            round(sum(r["completion_percent"] for r in recipients) / len(recipients), 1)
            if recipients else None
        ),
        "recipients": recipients,
    }


# --- Submission review -------------------------------------------------------


def _recipient_profile(db: Session, assignment: Assignment, student_id: uuid.UUID) -> StudentProfile:
    is_recipient = db.scalar(
        select(AssignmentRecipient.id).where(
            AssignmentRecipient.assignment_id == assignment.id,
            AssignmentRecipient.student_id == student_id,
        )
    )
    if is_recipient is None:
        raise NotFoundError("Student not found on this assignment.")
    return db.get(StudentProfile, student_id)


def _latest_submission(db: Session, assignment_id: uuid.UUID, student_id: uuid.UUID) -> Submission | None:
    return db.scalar(
        select(Submission)
        .where(Submission.assignment_id == assignment_id, Submission.student_id == student_id)
        .order_by(Submission.attempt_number.desc())
        .limit(1)
    )


def get_student_submission(
    db: Session, trainer: TrainerProfile, assignment_id: uuid.UUID, student_id: uuid.UUID
) -> dict:
    """A recipient's work on one assignment: every attempt per puzzle, with the
    moves played and hints used, plus their submission for review."""
    assignment = _get_owned_assignment(db, trainer, assignment_id)
    student = _recipient_profile(db, assignment, student_id)
    user = db.get(User, student.user_id)

    puzzles = db.execute(
        select(AssignmentPuzzle, Puzzle)
        .join(Puzzle, Puzzle.id == AssignmentPuzzle.puzzle_id)
        .where(AssignmentPuzzle.assignment_id == assignment.id)
        .order_by(AssignmentPuzzle.display_order, AssignmentPuzzle.id)
    ).all()
    attempts = db.scalars(
        select(PuzzleAttempt)
        .where(PuzzleAttempt.assignment_id == assignment.id, PuzzleAttempt.student_id == student.id)
        .order_by(PuzzleAttempt.attempted_at)
    ).all()

    by_puzzle: dict[uuid.UUID, list] = {}
    for attempt in attempts:
        by_puzzle.setdefault(attempt.puzzle_id, []).append(
            {
                "id": attempt.id,
                "is_solved": attempt.is_solved,
                "moves": attempt.moves,
                "hints_used": attempt.hints_used,
                "time_taken_seconds": attempt.time_taken_seconds,
                "attempted_at": attempt.attempted_at,
            }
        )

    items = []
    for link, puzzle in puzzles:
        tries = by_puzzle.get(puzzle.id, [])
        items.append(
            {
                "puzzle_id": puzzle.id,
                "display_order": link.display_order,
                "rating": puzzle.rating,
                "fen": puzzle.fen,
                "points": link.points,
                "solved": any(t["is_solved"] for t in tries),
                "attempts": tries,
            }
        )

    submission = _latest_submission(db, assignment.id, student.id)

    return {
        "assignment_id": assignment.id,
        "assignment_title": assignment.title,
        "student_id": student.id,
        "full_name": user.full_name,
        "email": user.email,
        "total_points": sum(link.points for link, _ in puzzles),
        "earned_points": sum(item["points"] for item in items if item["solved"]),
        "puzzles": items,
        "submission": _submission_item(submission) if submission else None,
    }


def _submission_item(submission: Submission) -> dict:
    return {
        "id": submission.id,
        "attempt_number": submission.attempt_number,
        "status": submission.status,
        "score": submission.score,
        "submitted_at": submission.submitted_at,
        "trainer_feedback": submission.trainer_feedback,
    }


def review_submission(
    db: Session,
    trainer: TrainerProfile,
    assignment_id: uuid.UUID,
    student_id: uuid.UUID,
    data: dict,
) -> dict:
    """Grade (or return for more work) a recipient's latest submission."""
    assignment = _get_owned_assignment(db, trainer, assignment_id)
    student = _recipient_profile(db, assignment, student_id)
    submission = _latest_submission(db, assignment.id, student.id)

    if submission is None:
        raise ConflictError("This student has not submitted the assignment yet.")

    total_points = db.scalar(
        select(func.coalesce(func.sum(AssignmentPuzzle.points), 0)).where(
            AssignmentPuzzle.assignment_id == assignment.id
        )
    )

    if data.get("score") is not None:
        if data["score"] > total_points:
            raise ValidationError(f"Score cannot exceed the assignment's {total_points} points.")
        submission.score = data["score"]

    submission.status = data["status"]
    submission.trainer_feedback = data.get("feedback")

    verb = "graded" if data["status"] == "graded" else "returned"
    notification_service.notify(
        db,
        [student.user_id],
        "submission_reviewed",
        f"Assignment {verb}: {assignment.title}",
        data.get("feedback") or f"Your trainer {verb} your submission.",
        {"assignment_id": assignment.id},
    )
    db.commit()

    return get_student_submission(db, trainer, assignment.id, student.id)
