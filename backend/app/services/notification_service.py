"""In-app notifications and the per-user preferences that filter them.

Notifications are queued in the caller's transaction (``db.add`` only), so a
notification exists exactly when the change it reports was committed.
Each notification type belongs to a preference category; users who switched
a category off in their account settings get no notifications of it.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import (
    Assignment,
    ClassSession,
    Notification,
    StudentProfile,
    TrainerProfile,
    User,
)
from app.services import email_service
from app.utils.pagination import PageParams, make_page, paginate

# Preference category -> default. Stored under users.settings["notifications"].
NOTIFICATION_CATEGORIES = {
    "sessions": True,
    "assignments": True,
    "feedback": True,
    "content": True,
    # Also send an email (delivery is only logged until email is configured).
    "email": False,
}

TYPE_CATEGORY = {
    "session_scheduled": "sessions",
    "session_updated": "sessions",
    "session_cancelled": "sessions",
    "assignment_published": "assignments",
    "assignment_completed": "assignments",
    "submission_reviewed": "assignments",
    "feedback_received": "feedback",
    "feedback_reviewed": "feedback",
    "post_published": "content",
}


def preferences(user: User) -> dict:
    stored = (user.settings or {}).get("notifications") or {}
    return {key: bool(stored.get(key, default)) for key, default in NOTIFICATION_CATEGORIES.items()}


def notify(
    db: Session,
    user_ids: Iterable[uuid.UUID],
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> int:
    """Queue one notification per user who has the category enabled.

    Returns the number queued. The caller commits.
    """
    category = TYPE_CATEGORY[notification_type]
    ids = list(dict.fromkeys(user_ids))

    if not ids:
        return 0

    users = db.scalars(select(User).where(User.id.in_(ids), User.is_active.is_(True))).all()
    queued = 0

    for user in users:
        prefs = preferences(user)

        if not prefs[category]:
            continue

        db.add(
            Notification(
                user_id=user.id,
                title=title[:200],
                message=message,
                notification_type=notification_type,
                data={key: str(value) for key, value in (data or {}).items()},
            )
        )
        queued += 1

        if prefs["email"]:
            email_service.send_email(user.email, title, message)

    return queued


# --- Domain events -----------------------------------------------------------


def _student_user_ids(db: Session, student_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    ids = list(student_ids)
    if not ids:
        return []
    return list(db.scalars(select(StudentProfile.user_id).where(StudentProfile.id.in_(ids))))


def _format_when(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def notify_session(db: Session, session: ClassSession, student_ids, event: str) -> int:
    verbs = {
        "session_scheduled": "New class scheduled",
        "session_updated": "Class updated",
        "session_cancelled": "Class cancelled",
    }
    return notify(
        db,
        _student_user_ids(db, student_ids),
        event,
        f"{verbs[event]}: {session.title}",
        f"{session.title} — {_format_when(session.start_time)}.",
        {"session_id": session.id},
    )


def notify_assignment_published(db: Session, assignment: Assignment, student_ids) -> int:
    due = f" Due {_format_when(assignment.due_date)}." if assignment.due_date else ""
    return notify(
        db,
        _student_user_ids(db, student_ids),
        "assignment_published",
        f"New assignment: {assignment.title}",
        f"Your trainer assigned {assignment.title}.{due}",
        {"assignment_id": assignment.id},
    )


def notify_assignment_completed(db: Session, assignment: Assignment, student: StudentProfile) -> int:
    trainer_user_id = db.scalar(
        select(TrainerProfile.user_id).where(TrainerProfile.id == assignment.trainer_id)
    )
    student_name = db.scalar(select(User.full_name).where(User.id == student.user_id))
    return notify(
        db,
        [trainer_user_id] if trainer_user_id else [],
        "assignment_completed",
        f"Submission: {assignment.title}",
        f"{student_name} completed {assignment.title}.",
        {"assignment_id": assignment.id, "student_id": student.user_id},
    )


# --- Inbox -------------------------------------------------------------------


def _item(row: Notification) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "message": row.message,
        "notification_type": row.notification_type,
        "is_read": row.is_read,
        "read_at": row.read_at,
        "data": row.data,
        "created_at": row.created_at,
    }


def list_notifications(db: Session, user: User, params: PageParams, unread_only: bool) -> dict:
    query = select(Notification).where(Notification.user_id == user.id)

    if unread_only:
        query = query.where(Notification.is_read.is_(False))

    rows, total = paginate(
        db, query.order_by(Notification.created_at.desc(), Notification.id), params
    )
    page = make_page([_item(row[0]) for row in rows], total, params)
    page["unread"] = unread_count(db, user)
    return page


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count()).where(
            Notification.user_id == user.id, Notification.is_read.is_(False)
        )
    ) or 0


def mark_read(db: Session, user: User, notification_id: uuid.UUID) -> dict:
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )

    if row is None:
        raise NotFoundError("Notification not found.")

    if not row.is_read:
        row.is_read = True
        row.read_at = datetime.now(timezone.utc)
        db.commit()

    return _item(row)


def mark_all_read(db: Session, user: User) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return result.rowcount
