"""Trainer training sessions and attendance.

Times are timezone-aware and stored in UTC; clients display them in the
viewer's local timezone. Lifecycle: scheduled -> completed, or
scheduled/ongoing -> cancelled. Only upcoming scheduled sessions can be
edited. Attendance can be recorded once a session has started and while it
is not cancelled; recording again for a student updates their record.

Session types: a 'group' session is for every member of its group. An
'individual' session is for the students the trainer selected when
scheduling it; its roster is the attendance rows created at that moment
(status 'scheduled' until attendance is recorded), and only those students
see it.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.services import notification_service
from app.models import (
    ClassSession,
    Group,
    GroupMember,
    SessionAttendance,
    StudentProfile,
    TrainerProfile,
    User,
)
from app.services.trainer_access import (
    get_active_owned_group,
    get_owned_group,
    group_member_ids,
    like_pattern,
)
from app.utils.pagination import PageParams, make_page, paginate

ACTIVE_STATUSES = ("scheduled", "ongoing")
RECORDED_ATTENDANCE = ("present", "absent", "late", "excused")

Scope = Literal["all", "upcoming", "past", "active", "completed"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _active_condition(now: datetime):
    """In progress: marked ongoing, or scheduled and inside its time slot."""
    return (ClassSession.status == "ongoing") | (
        (ClassSession.status == "scheduled")
        & (ClassSession.start_time <= now)
        & (ClassSession.end_time > now)
    )


def is_active(session: ClassSession, now: datetime | None = None) -> bool:
    now = now or _now()
    return session.status == "ongoing" or (
        session.status == "scheduled" and session.start_time <= now < session.end_time
    )


def can_edit(session: ClassSession) -> bool:
    return session.status == "scheduled" and session.start_time > _now()


def can_record_attendance(session: ClassSession) -> bool:
    return session.status != "cancelled" and session.start_time <= _now()


def _summary_query(trainer: TrainerProfile):
    roster = (
        select(GroupMember.group_id, func.count().label("roster_size"))
        .group_by(GroupMember.group_id)
        .subquery()
    )
    recorded = (
        select(
            SessionAttendance.session_id,
            func.count().filter(SessionAttendance.status.in_(RECORDED_ATTENDANCE)).label("recorded"),
            func.count().label("invited"),
        )
        .group_by(SessionAttendance.session_id)
        .subquery()
    )
    roster_size = case(
        (ClassSession.session_type == "individual", func.coalesce(recorded.c.invited, 0)),
        else_=func.coalesce(roster.c.roster_size, 0),
    )

    return (
        select(
            ClassSession,
            Group.name.label("group_name"),
            roster_size.label("roster_size"),
            func.coalesce(recorded.c.recorded, 0).label("attendance_recorded"),
        )
        .outerjoin(Group, Group.id == ClassSession.group_id)
        .outerjoin(roster, roster.c.group_id == ClassSession.group_id)
        .outerjoin(recorded, recorded.c.session_id == ClassSession.id)
        .where(ClassSession.trainer_id == trainer.id)
    )


def _summary(row) -> dict:
    session = row.ClassSession
    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "session_type": session.session_type,
        "is_active": is_active(session),
        "group": (
            {"id": session.group_id, "name": row.group_name}
            if session.group_id else None
        ),
        "start_time": session.start_time,
        "end_time": session.end_time,
        "learning_objective": session.learning_objective,
        "meeting_url": session.meeting_url,
        "roster_size": row.roster_size,
        "attendance_recorded": row.attendance_recorded,
    }


def list_sessions(
    db: Session,
    trainer: TrainerProfile,
    params: PageParams,
    *,
    scope: Scope = "all",
    status: str | None = None,
    group_id: uuid.UUID | None = None,
    search: str | None = None,
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
) -> dict:
    query = _summary_query(trainer)
    now = _now()

    if scope == "upcoming":
        query = query.where(ClassSession.start_time >= now, ClassSession.status.in_(ACTIVE_STATUSES))
        order = ClassSession.start_time.asc()
    elif scope == "past":
        query = query.where(
            (ClassSession.start_time < now) | (ClassSession.status.in_(("completed", "cancelled")))
        )
        order = ClassSession.start_time.desc()
    elif scope == "active":
        query = query.where(_active_condition(now))
        order = ClassSession.start_time.asc()
    elif scope == "completed":
        query = query.where(ClassSession.status == "completed")
        order = ClassSession.start_time.desc()
    else:
        order = ClassSession.start_time.desc()

    if status:
        query = query.where(ClassSession.status == status)
    if group_id:
        get_owned_group(db, trainer, group_id)
        query = query.where(ClassSession.group_id == group_id)
    if search and search.strip():
        query = query.where(ClassSession.title.ilike(like_pattern(search)))
    if starts_after:
        query = query.where(ClassSession.start_time >= starts_after)
    if starts_before:
        query = query.where(ClassSession.start_time < starts_before)

    rows, total = paginate(db, query.order_by(order, ClassSession.id), params)
    return make_page([_summary(row) for row in rows], total, params)


def upcoming_sessions(db: Session, trainer: TrainerProfile, limit: int = 5) -> list[dict]:
    rows = db.execute(
        _summary_query(trainer)
        .where(ClassSession.start_time >= _now(), ClassSession.status.in_(ACTIVE_STATUSES))
        .order_by(ClassSession.start_time.asc())
        .limit(limit)
    )
    return [_summary(row) for row in rows]


def recent_completed_sessions(db: Session, trainer: TrainerProfile, limit: int = 5) -> list[dict]:
    rows = db.execute(
        _summary_query(trainer)
        .where(ClassSession.status == "completed")
        .order_by(ClassSession.start_time.desc())
        .limit(limit)
    )
    return [_summary(row) for row in rows]


def _get_owned_session(db: Session, trainer: TrainerProfile, session_id: uuid.UUID) -> ClassSession:
    session = db.get(ClassSession, session_id)

    if session is None or session.trainer_id != trainer.id:
        raise NotFoundError("Session not found.")

    return session


def get_session(db: Session, trainer: TrainerProfile, session_id: uuid.UUID) -> dict:
    row = db.execute(_summary_query(trainer).where(ClassSession.id == session_id)).first()

    if row is None:
        raise NotFoundError("Session not found.")

    session = row.ClassSession
    roster = []
    invited = select(SessionAttendance.student_id).where(SessionAttendance.session_id == session.id)

    if session.session_type == "individual":
        on_roster = invited.subquery()
    elif session.group_id:
        # Current members, plus anyone with a record who has since left.
        on_roster = (
            select(GroupMember.student_id).where(GroupMember.group_id == session.group_id)
            .union(invited)
            .subquery()
        )
    else:
        on_roster = None

    if on_roster is not None:
        roster = [
            row._asdict()
            for row in db.execute(
                select(
                    StudentProfile.id.label("student_id"),
                    User.full_name,
                    User.email,
                    SessionAttendance.status.label("attendance_status"),
                    SessionAttendance.remarks,
                )
                .join(User, User.id == StudentProfile.user_id)
                .outerjoin(
                    SessionAttendance,
                    and_(
                        SessionAttendance.student_id == StudentProfile.id,
                        SessionAttendance.session_id == session.id,
                    ),
                )
                .where(StudentProfile.id.in_(select(on_roster.c.student_id)))
                .order_by(User.full_name)
            )
        ]

    for entry in roster:
        # 'scheduled' is the schema's placeholder for "not yet recorded".
        if entry["attendance_status"] == "scheduled":
            entry["attendance_status"] = None

    summary = {status: 0 for status in RECORDED_ATTENDANCE}
    for entry in roster:
        if entry["attendance_status"] in summary:
            summary[entry["attendance_status"]] += 1

    return {
        **_summary(row),
        "description": session.description,
        "can_edit": can_edit(session),
        "can_record_attendance": can_record_attendance(session),
        "roster": roster,
        "attendance_summary": {
            **summary,
            "unrecorded": sum(1 for entry in roster if entry["attendance_status"] is None),
        },
    }


def _check_overlap(
    db: Session,
    trainer: TrainerProfile,
    start_time: datetime,
    end_time: datetime,
    exclude_id: uuid.UUID | None = None,
) -> None:
    conditions = [
        ClassSession.trainer_id == trainer.id,
        ClassSession.status.in_(ACTIVE_STATUSES),
        ClassSession.start_time < end_time,
        ClassSession.end_time > start_time,
    ]
    if exclude_id:
        conditions.append(ClassSession.id != exclude_id)

    if db.scalar(select(exists().where(*conditions))):
        raise ConflictError("This time overlaps another of your scheduled sessions.")


def _check_times(start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise ValidationError("End time must be after start time.")
    if start_time <= _now():
        raise ValidationError("Sessions must be scheduled in the future.")


def session_student_ids(db: Session, session: ClassSession) -> set[uuid.UUID]:
    """Students a session is for: its invitees, or its group's members."""
    invited = set(
        db.scalars(select(SessionAttendance.student_id).where(SessionAttendance.session_id == session.id))
    )
    if session.session_type == "individual" or session.group_id is None:
        return invited
    return group_member_ids(db, session.group_id) | invited


def create_session(db: Session, trainer: TrainerProfile, data: dict) -> dict:
    group = get_active_owned_group(db, trainer, data["group_id"])
    _check_times(data["start_time"], data["end_time"])
    _check_overlap(db, trainer, data["start_time"], data["end_time"])

    selected = data.get("student_ids")
    members = group_member_ids(db, group.id)

    if selected is not None and set(selected) - members:
        raise ValidationError("Selected students must be members of the session's group.")

    session = ClassSession(
        trainer_id=trainer.id,
        group_id=group.id,
        title=data["title"].strip(),
        description=data.get("description"),
        learning_objective=data.get("learning_objective"),
        session_type="individual" if selected is not None else "group",
        start_time=data["start_time"],
        end_time=data["end_time"],
        meeting_url=data.get("meeting_url"),
        status="scheduled",
    )
    db.add(session)
    db.flush()

    for student_id in selected or []:
        db.add(SessionAttendance(session_id=session.id, student_id=student_id, status="scheduled"))

    notification_service.notify_session(
        db, session, selected if selected is not None else members, "session_scheduled"
    )
    db.commit()

    return get_session(db, trainer, session.id)


def update_session(db: Session, trainer: TrainerProfile, session_id: uuid.UUID, changes: dict) -> dict:
    session = _get_owned_session(db, trainer, session_id)

    if not can_edit(session):
        raise ConflictError("Only upcoming scheduled sessions can be edited.")

    rescheduled = False

    if "start_time" in changes or "end_time" in changes:
        start_time = changes.get("start_time") or session.start_time
        end_time = changes.get("end_time") or session.end_time
        _check_times(start_time, end_time)
        _check_overlap(db, trainer, start_time, end_time, exclude_id=session.id)
        rescheduled = (start_time, end_time) != (session.start_time, session.end_time)
        session.start_time, session.end_time = start_time, end_time

    if changes.get("title"):
        session.title = changes["title"].strip()
    for field in ("description", "learning_objective", "meeting_url"):
        if field in changes:
            setattr(session, field, changes[field])

    if rescheduled or "meeting_url" in changes:
        notification_service.notify_session(
            db, session, session_student_ids(db, session), "session_updated"
        )

    db.commit()
    return get_session(db, trainer, session.id)


def change_session_status(db: Session, trainer: TrainerProfile, session_id: uuid.UUID, action: str) -> dict:
    session = _get_owned_session(db, trainer, session_id)

    if action == "cancel":
        if session.status not in ACTIVE_STATUSES:
            raise ConflictError(f"Cannot cancel a session that is {session.status}.")
        session.status = "cancelled"
        notification_service.notify_session(
            db, session, session_student_ids(db, session), "session_cancelled"
        )
    elif action == "complete":
        if session.status not in ACTIVE_STATUSES:
            raise ConflictError(f"Cannot complete a session that is {session.status}.")
        if session.start_time > _now():
            raise ConflictError("A session cannot be completed before it starts.")
        session.status = "completed"

    db.commit()
    return get_session(db, trainer, session.id)


def record_attendance(db: Session, trainer: TrainerProfile, session_id: uuid.UUID, records: list[dict]) -> dict:
    session = _get_owned_session(db, trainer, session_id)

    if session.status == "cancelled":
        raise ConflictError("Attendance cannot be recorded for a cancelled session.")
    if session.start_time > _now():
        raise ConflictError("Attendance can be recorded once the session has started.")
    existing = {
        record.student_id: record
        for record in db.scalars(
            select(SessionAttendance).where(SessionAttendance.session_id == session.id)
        )
    }
    allowed = session_student_ids(db, session)

    if not allowed:
        raise ConflictError("This session has no roster.")

    outside = {record["student_id"] for record in records} - allowed
    if outside:
        raise ValidationError("Attendance can only be recorded for students on the session roster.")

    for record in records:
        current = existing.get(record["student_id"])
        if current is None:
            db.add(SessionAttendance(
                session_id=session.id,
                student_id=record["student_id"],
                status=record["status"],
                remarks=record.get("remarks"),
            ))
        else:
            current.status = record["status"]
            current.remarks = record.get("remarks")

    db.commit()
    return get_session(db, trainer, session.id)
