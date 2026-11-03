"""Feedback: students to their trainers, trainers to the admin team.

* A student can write to their primary trainer or the trainer of any group
  they belong to, optionally with a 1-5 rating.
* A trainer writes to the admin team (``audience='admin'``); every admin
  sees it.
* Recipients review feedback (status ``reviewed`` plus an optional
  response), and the sender is notified. Admins can read all feedback;
  trainers see only feedback addressed to them; senders see what they sent.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.models import Feedback, Group, GroupMember, StudentProfile, TrainerProfile, User
from app.services import notification_service
from app.utils.pagination import PageParams, make_page, paginate


def student_trainers(db: Session, user: User) -> list[dict]:
    """Trainers a student may write to: primary trainer and group trainers."""
    student = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if student is None:
        return []

    trainer_ids = {student.trainer_id} | set(
        db.scalars(
            select(Group.trainer_id)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.student_id == student.id)
        )
    )
    rows = db.execute(
        select(User.id, User.full_name)
        .join(TrainerProfile, TrainerProfile.user_id == User.id)
        .where(TrainerProfile.id.in_(trainer_ids), User.is_active.is_(True))
        .order_by(User.full_name)
    ).all()
    return [{"id": row.id, "name": row.full_name} for row in rows]


def recipients(db: Session, user: User) -> list[dict]:
    if user.role == "student":
        return student_trainers(db, user)
    if user.role == "trainer":
        return [{"id": None, "name": "Academy admins"}]
    return []


def submit(db: Session, user: User, data: dict) -> dict:
    if user.role == "student":
        allowed = {item["id"] for item in student_trainers(db, user)}
        if data.get("to_user_id") not in allowed:
            raise ValidationError("You can send feedback only to your own trainers.")
        audience, to_user_id = "trainer", data["to_user_id"]
        notify_ids = [to_user_id]
    elif user.role == "trainer":
        if data.get("rating") is not None:
            raise ValidationError("Ratings are only for feedback about trainers.")
        audience, to_user_id = "admin", None
        notify_ids = list(
            db.scalars(select(User.id).where(User.role == "admin", User.is_active.is_(True)))
        )
    else:
        raise PermissionDeniedError("Admins review feedback; they do not send it.")

    feedback = Feedback(
        from_user_id=user.id,
        to_user_id=to_user_id,
        audience=audience,
        message=data["message"].strip(),
        category=data.get("category"),
        rating=data.get("rating"),
        status="open",
    )
    db.add(feedback)
    db.flush()
    notification_service.notify(
        db,
        notify_ids,
        "feedback_received",
        f"New feedback from {user.full_name}",
        feedback.message[:300],
        {"feedback_id": feedback.id},
    )
    db.commit()
    return get_feedback(db, user, feedback.id)


def _base_query():
    sender = aliased(User)
    recipient = aliased(User)
    reviewer = aliased(User)
    query = (
        select(
            Feedback,
            sender.full_name.label("from_name"),
            sender.role.label("from_role"),
            recipient.full_name.label("to_name"),
            reviewer.full_name.label("reviewer_name"),
        )
        .join(sender, sender.id == Feedback.from_user_id)
        .outerjoin(recipient, recipient.id == Feedback.to_user_id)
        .outerjoin(reviewer, reviewer.id == Feedback.reviewed_by)
    )
    return query


def _readable(user: User):
    if user.role == "admin":
        return Feedback.id.is_not(None)
    return or_(Feedback.from_user_id == user.id, Feedback.to_user_id == user.id)


def _can_review(user: User, feedback: Feedback) -> bool:
    if feedback.audience == "admin":
        return user.role == "admin"
    return feedback.to_user_id == user.id


def _item(row, user: User) -> dict:
    feedback = row.Feedback
    return {
        "id": feedback.id,
        "audience": feedback.audience,
        "from_user_id": feedback.from_user_id,
        "from_name": row.from_name,
        "from_role": row.from_role,
        "to_user_id": feedback.to_user_id,
        "to_name": row.to_name or ("Academy admins" if feedback.audience == "admin" else None),
        "message": feedback.message,
        "category": feedback.category,
        "rating": feedback.rating,
        "status": feedback.status,
        "response": feedback.response,
        "reviewer_name": row.reviewer_name,
        "reviewed_at": feedback.reviewed_at,
        "created_at": feedback.created_at,
        "can_review": _can_review(user, feedback),
    }


def list_feedback(
    db: Session, user: User, params: PageParams, box: str, status: str | None = None
) -> dict:
    """``box``: 'inbox' (to review), 'sent', or 'all' (admins only)."""
    query = _base_query()

    if box == "sent":
        query = query.where(Feedback.from_user_id == user.id)
    elif box == "inbox":
        if user.role == "admin":
            query = query.where(Feedback.audience == "admin")
        else:
            query = query.where(Feedback.audience == "trainer", Feedback.to_user_id == user.id)
    elif box == "all":
        if user.role != "admin":
            raise PermissionDeniedError("Only admins can list all feedback.")
    if status:
        query = query.where(Feedback.status == status)

    rows, total = paginate(db, query.order_by(Feedback.created_at.desc(), Feedback.id), params)
    return make_page([_item(row, user) for row in rows], total, params)


def get_feedback(db: Session, user: User, feedback_id: uuid.UUID) -> dict:
    row = db.execute(_base_query().where(Feedback.id == feedback_id, _readable(user))).first()
    if row is None:
        raise NotFoundError("Feedback not found.")
    return _item(row, user)


def review(db: Session, user: User, feedback_id: uuid.UUID, response: str | None) -> dict:
    feedback = db.scalar(select(Feedback).where(Feedback.id == feedback_id, _readable(user)))

    if feedback is None:
        raise NotFoundError("Feedback not found.")
    if not _can_review(user, feedback):
        raise PermissionDeniedError("Only the recipient can review this feedback.")

    feedback.status = "reviewed"
    feedback.response = response.strip() if response and response.strip() else None
    feedback.reviewed_by = user.id
    feedback.reviewed_at = datetime.now(timezone.utc)

    notification_service.notify(
        db,
        [feedback.from_user_id],
        "feedback_reviewed",
        "Your feedback was reviewed",
        feedback.response or f"{user.full_name} reviewed your feedback.",
        {"feedback_id": feedback.id},
    )
    db.commit()
    return get_feedback(db, user, feedback.id)
