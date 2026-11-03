"""Business rules for administrative user and group management."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.security import hash_password
from app.models import (
    Assignment,
    AssignmentRecipient,
    AuditLog,
    ClassSession,
    Group,
    GroupMember,
    StudentProfile,
    StudentProgress,
    Submission,
    TrainerProfile,
    User,
)
from app.services.auth_service import revoke_all_refresh_tokens
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.utils.pagination import PageParams, build_page, count_rows

STUDENT_ASSIGNMENT_LIMIT = 50


@dataclass
class AdminContext:
    """The acting admin and request metadata recorded in the audit log."""

    actor: User
    ip_address: str | None = None


def like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def user_ref(user_id, full_name, email) -> dict | None:
    if user_id is None:
        return None
    return {"id": user_id, "full_name": full_name, "email": email}


def record_audit(
    db: Session,
    ctx: AdminContext,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    details: dict | None = None,
) -> None:
    """Add an audit entry; the caller commits. Never pass secrets in details."""
    db.add(
        AuditLog(
            actor_id=ctx.actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ctx.ip_address,
        )
    )


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(conflict_message)


# ----- Lookups -------------------------------------------------------------


def _get_user(db: Session, user_id: uuid.UUID, role: str | None = None) -> User:
    user = db.get(User, user_id)

    if user is None or (role is not None and user.role != role):
        raise NotFoundError(f"{(role or 'user').capitalize()} not found.")

    return user


def _trainer_profile_for(db: Session, user_id: uuid.UUID) -> TrainerProfile | None:
    return db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == user_id))


def _student_profile_for(db: Session, user_id: uuid.UUID) -> StudentProfile | None:
    return db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))


def _resolve_trainer(db: Session, trainer_user_id: uuid.UUID) -> TrainerProfile:
    """Return the profile of an active trainer referenced in a request body."""
    row = db.execute(
        select(User, TrainerProfile)
        .outerjoin(TrainerProfile, TrainerProfile.user_id == User.id)
        .where(User.id == trainer_user_id)
    ).first()

    if row is None or row.User.role != "trainer":
        raise ValidationError(f"Trainer {trainer_user_id} does not exist.")

    if not row.User.is_active:
        raise ValidationError("The selected trainer account is inactive.")

    if row.TrainerProfile is None:
        raise ValidationError("The selected trainer has no trainer profile.")

    return row.TrainerProfile


def _email_taken(db: Session, email: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(User.id).where(func.lower(User.email) == email)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return db.scalar(stmt) is not None


def _lock_active_admin_ids(db: Session) -> list[uuid.UUID]:
    # Row locks serialise concurrent demotions so two admins cannot remove
    # each other at the same time and leave the platform without an admin.
    return list(
        db.scalars(
            select(User.id)
            .where(User.role == "admin", User.is_active.is_(True))
            .with_for_update()
        )
    )


def ensure_other_active_admin(db: Session, user_id: uuid.UUID) -> None:
    """Fail if ``user_id`` is the last active admin."""
    if not any(admin_id != user_id for admin_id in _lock_active_admin_ids(db)):
        raise ConflictError("At least one active admin account must remain.")


# ----- User listing and details --------------------------------------------


def _search_users(stmt, search: str | None, user=User):
    if search and search.strip():
        pattern = like_pattern(search.strip())
        stmt = stmt.where(
            or_(
                user.full_name.ilike(pattern, escape="\\"),
                user.email.ilike(pattern, escape="\\"),
            )
        )
    return stmt


def list_users(
    db: Session,
    params: PageParams,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> dict:
    stmt = _search_users(select(User), search)

    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total = count_rows(db, stmt)
    users = db.scalars(
        stmt.order_by(User.created_at.desc(), User.id)
        .offset(params.offset)
        .limit(params.page_size)
    ).all()

    return build_page(list(users), total, params)


def _trainer_stats(db: Session, profile: TrainerProfile) -> dict:
    group_count, active_group_count = db.execute(
        select(
            func.count(),
            func.count().filter(Group.is_active.is_(True)),
        ).where(Group.trainer_id == profile.id)
    ).one()

    return {
        "group_count": group_count,
        "active_group_count": active_group_count,
        "primary_student_count": db.scalar(
            select(func.count()).where(StudentProfile.trainer_id == profile.id)
        ),
        "group_student_count": db.scalar(
            select(func.count(func.distinct(GroupMember.student_id)))
            .join(Group, Group.id == GroupMember.group_id)
            .where(Group.trainer_id == profile.id)
        ),
        "upcoming_session_count": db.scalar(
            select(func.count()).where(
                ClassSession.trainer_id == profile.id,
                ClassSession.status == "scheduled",
                ClassSession.start_time > datetime.now(timezone.utc),
            )
        ),
        "assignment_count": db.scalar(
            select(func.count()).where(Assignment.trainer_id == profile.id)
        ),
    }


def _student_assignments(db: Session, profile: StudentProfile) -> list[dict]:
    attempts = (
        select(
            Submission.assignment_id,
            func.count().label("attempts"),
            func.max(Submission.attempt_number).label("latest_attempt"),
        )
        .where(Submission.student_id == profile.id)
        .group_by(Submission.assignment_id)
        .subquery()
    )
    latest = aliased(Submission)
    trainer_user = aliased(User)

    rows = db.execute(
        select(
            Assignment,
            trainer_user.id.label("trainer_id"),
            trainer_user.full_name.label("trainer_name"),
            trainer_user.email.label("trainer_email"),
            attempts.c.attempts,
            latest.status.label("latest_status"),
            latest.score.label("latest_score"),
        )
        .join(AssignmentRecipient, AssignmentRecipient.assignment_id == Assignment.id)
        .join(TrainerProfile, TrainerProfile.id == Assignment.trainer_id)
        .join(trainer_user, trainer_user.id == TrainerProfile.user_id)
        .outerjoin(attempts, attempts.c.assignment_id == Assignment.id)
        .outerjoin(
            latest,
            and_(
                latest.assignment_id == Assignment.id,
                latest.student_id == profile.id,
                latest.attempt_number == attempts.c.latest_attempt,
            ),
        )
        .where(AssignmentRecipient.student_id == profile.id)
        .order_by(Assignment.created_at.desc())
        .limit(STUDENT_ASSIGNMENT_LIMIT)
    ).all()

    return [
        {
            "id": row.Assignment.id,
            "title": row.Assignment.title,
            "status": row.Assignment.status,
            "due_date": row.Assignment.due_date,
            "trainer": user_ref(row.trainer_id, row.trainer_name, row.trainer_email),
            "latest_submission_status": row.latest_status,
            "latest_score": row.latest_score,
            "attempts": row.attempts or 0,
        }
        for row in rows
    ]


def get_user_detail(db: Session, user_id: uuid.UUID, role: str | None = None) -> dict:
    user = _get_user(db, user_id, role)
    detail = {
        **{
            column: getattr(user, column)
            for column in (
                "id", "email", "full_name", "role", "phone", "avatar_url",
                "language", "is_active", "is_verified", "last_login_at",
                "created_at", "updated_at",
            )
        },
        "trainer_profile": None,
        "student_profile": None,
        "groups": [],
        "trainer_stats": None,
        "student_progress": None,
        "assignments": [],
    }

    trainer_profile = _trainer_profile_for(db, user.id)
    if trainer_profile is not None:
        detail["trainer_profile"] = trainer_profile
        detail["trainer_stats"] = _trainer_stats(db, trainer_profile)

        if user.role == "trainer":
            detail["groups"] = list(
                db.scalars(
                    select(Group)
                    .where(Group.trainer_id == trainer_profile.id)
                    .order_by(Group.name)
                )
            )

    trainer_user = aliased(User)
    student_row = db.execute(
        select(StudentProfile, trainer_user.id, trainer_user.full_name, trainer_user.email)
        .join(TrainerProfile, TrainerProfile.id == StudentProfile.trainer_id)
        .join(trainer_user, trainer_user.id == TrainerProfile.user_id)
        .where(StudentProfile.user_id == user.id)
    ).first()

    if student_row is not None:
        profile = student_row.StudentProfile
        detail["student_profile"] = {
            "id": profile.id,
            "date_of_birth": profile.date_of_birth,
            "chess_rating": profile.chess_rating,
            "level": profile.level,
            "notes": profile.notes,
            "trainer": user_ref(student_row[1], student_row[2], student_row[3]),
        }
        detail["student_progress"] = db.scalar(
            select(StudentProgress).where(StudentProgress.student_id == profile.id)
        )
        detail["assignments"] = _student_assignments(db, profile)

        if user.role == "student":
            detail["groups"] = list(
                db.scalars(
                    select(Group)
                    .join(GroupMember, GroupMember.group_id == Group.id)
                    .where(GroupMember.student_id == profile.id)
                    .order_by(Group.name)
                )
            )

    return detail


def list_trainers(
    db: Session,
    params: PageParams,
    search: str | None = None,
    is_active: bool | None = None,
) -> dict:
    group_counts = (
        select(Group.trainer_id, func.count().label("n"))
        .group_by(Group.trainer_id)
        .subquery()
    )
    student_counts = (
        select(StudentProfile.trainer_id, func.count().label("n"))
        .group_by(StudentProfile.trainer_id)
        .subquery()
    )

    stmt = (
        select(
            User,
            TrainerProfile.specialization,
            TrainerProfile.experience_years,
            func.coalesce(group_counts.c.n, 0).label("group_count"),
            func.coalesce(student_counts.c.n, 0).label("student_count"),
        )
        .outerjoin(TrainerProfile, TrainerProfile.user_id == User.id)
        .outerjoin(group_counts, group_counts.c.trainer_id == TrainerProfile.id)
        .outerjoin(student_counts, student_counts.c.trainer_id == TrainerProfile.id)
        .where(User.role == "trainer")
    )
    stmt = _search_users(stmt, search)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(User.full_name, User.id).offset(params.offset).limit(params.page_size)
    ).all()

    items = [
        {
            **_summary(row.User),
            "specialization": row.specialization,
            "experience_years": row.experience_years,
            "group_count": row.group_count,
            "primary_student_count": row.student_count,
        }
        for row in rows
    ]
    return build_page(items, total, params)


def list_students(
    db: Session,
    params: PageParams,
    search: str | None = None,
    is_active: bool | None = None,
    level: str | None = None,
    trainer_user_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    exclude_group_id: uuid.UUID | None = None,
) -> dict:
    trainer_user = aliased(User)
    group_counts = (
        select(GroupMember.student_id, func.count().label("n"))
        .group_by(GroupMember.student_id)
        .subquery()
    )

    # Outer joins keep self-registered students, who have no profile yet.
    stmt = (
        select(
            User,
            StudentProfile.level,
            StudentProfile.chess_rating,
            trainer_user.id.label("trainer_id"),
            trainer_user.full_name.label("trainer_name"),
            trainer_user.email.label("trainer_email"),
            func.coalesce(group_counts.c.n, 0).label("group_count"),
            func.coalesce(StudentProgress.total_xp, 0).label("total_xp"),
        )
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .outerjoin(TrainerProfile, TrainerProfile.id == StudentProfile.trainer_id)
        .outerjoin(trainer_user, trainer_user.id == TrainerProfile.user_id)
        .outerjoin(group_counts, group_counts.c.student_id == StudentProfile.id)
        .outerjoin(StudentProgress, StudentProgress.student_id == StudentProfile.id)
        .where(User.role == "student")
    )
    stmt = _search_users(stmt, search)

    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if level:
        stmt = stmt.where(StudentProfile.level == level)
    if trainer_user_id:
        stmt = stmt.where(trainer_user.id == trainer_user_id)

    membership = exists().where(
        GroupMember.student_id == StudentProfile.id,
        GroupMember.group_id == (group_id or exclude_group_id),
    )
    if group_id:
        stmt = stmt.where(membership)
    elif exclude_group_id:
        stmt = stmt.where(~membership)

    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(User.full_name, User.id).offset(params.offset).limit(params.page_size)
    ).all()

    items = [
        {
            **_summary(row.User),
            "level": row.level,
            "chess_rating": row.chess_rating,
            "trainer": user_ref(row.trainer_id, row.trainer_name, row.trainer_email),
            "group_count": row.group_count,
            "total_xp": row.total_xp,
        }
        for row in rows
    ]
    return build_page(items, total, params)


def _summary(user: User) -> dict:
    return {
        column: getattr(user, column)
        for column in (
            "id", "email", "full_name", "role", "phone", "avatar_url",
            "language", "is_active", "is_verified", "last_login_at",
            "created_at", "updated_at",
        )
    }


# ----- Account creation and updates ----------------------------------------


def create_account(
    db: Session,
    ctx: AdminContext,
    *,
    role: str,
    email: str,
    password: str,
    full_name: str,
    phone: str | None = None,
    trainer_profile: dict | None = None,
    student_profile: dict | None = None,
) -> dict:
    """Create a trainer or student account together with its profile."""
    if role not in {"trainer", "student"}:
        raise ValidationError("Only trainer and student accounts can be created.")

    email = email.strip().lower()
    if _email_taken(db, email):
        raise ConflictError("Email is already registered.")

    student_trainer = None
    if role == "student":
        student_profile = dict(student_profile or {})
        trainer_user_id = student_profile.pop("trainer_user_id", None)
        if trainer_user_id is None:
            raise ValidationError("A student must be assigned a trainer.")
        student_trainer = _resolve_trainer(db, trainer_user_id)

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        phone=phone,
        role=role,
    )
    db.add(user)
    db.flush()

    if role == "trainer":
        db.add(TrainerProfile(user_id=user.id, **(trainer_profile or {})))
    else:
        db.add(
            StudentProfile(
                user_id=user.id,
                trainer_id=student_trainer.id,
                **student_profile,
            )
        )

    record_audit(db, ctx, f"{role}.created", "user", user.id, {"email": email, "role": role})
    _commit(db, "Email is already registered.")

    return get_user_detail(db, user.id)


def update_user(db: Session, ctx: AdminContext, user_id: uuid.UUID, changes: dict) -> dict:
    """Apply a partial profile update. ``changes`` comes from ``exclude_unset``."""
    user = _get_user(db, user_id)
    trainer_changes = changes.pop("trainer_profile", None)
    student_changes = changes.pop("student_profile", None)

    if "email" in changes:
        email = changes["email"].strip().lower()
        if email != user.email:
            if _email_taken(db, email, exclude_id=user.id):
                raise ConflictError("Email is already registered.")
            changes["email"] = email
            # The new address has not been confirmed by its owner.
            user.is_verified = False
        else:
            changes.pop("email")

    for field, value in changes.items():
        setattr(user, field, value)

    if trainer_changes:
        if user.role != "trainer":
            raise ValidationError("Only trainers have a trainer profile.")
        profile = _trainer_profile_for(db, user.id)
        if profile is None:
            profile = TrainerProfile(user_id=user.id)
            db.add(profile)
        for field, value in trainer_changes.items():
            if field == "experience_years" and value is None:
                continue
            setattr(profile, field, value)

    if student_changes:
        if user.role != "student":
            raise ValidationError("Only students have a student profile.")
        student_changes = dict(student_changes)
        trainer_user_id = student_changes.pop("trainer_user_id", None)
        profile = _student_profile_for(db, user.id)

        if profile is None:
            if trainer_user_id is None:
                raise ValidationError(
                    "Assign a trainer to create this student's profile."
                )
            profile = StudentProfile(user_id=user.id)
            db.add(profile)

        if trainer_user_id is not None:
            profile.trainer_id = _resolve_trainer(db, trainer_user_id).id

        for field, value in student_changes.items():
            if field in {"chess_rating", "level"} and value is None:
                continue
            setattr(profile, field, value)

    changed = sorted(
        list(changes)
        + [f"trainer_profile.{f}" for f in trainer_changes or {}]
        + [f"student_profile.{f}" for f in student_changes or {}]
    )
    record_audit(db, ctx, "user.updated", "user", user.id, {"fields": changed})
    _commit(db, "Email is already registered.")

    return get_user_detail(db, user.id)


def change_role(
    db: Session,
    ctx: AdminContext,
    user_id: uuid.UUID,
    new_role: str,
    trainer_user_id: uuid.UUID | None = None,
) -> dict:
    """Change a user's role while keeping related records consistent.

    Profiles are kept when a user leaves a role, so history such as past
    sessions and assignments stays intact.
    """
    user = _get_user(db, user_id)
    old_role = user.role

    if user.id == ctx.actor.id:
        raise ConflictError("You cannot change your own role.")

    if new_role == old_role:
        return get_user_detail(db, user.id)

    if old_role == "admin" and user.is_active:
        ensure_other_active_admin(db, user.id)

    if old_role == "trainer":
        profile = _trainer_profile_for(db, user.id)
        if profile is not None:
            stats = _trainer_stats(db, profile)
            if stats["group_count"] or stats["primary_student_count"]:
                raise ConflictError(
                    "Reassign this trainer's groups "
                    f"({stats['group_count']}) and students "
                    f"({stats['primary_student_count']}) before changing the role."
                )

    if old_role == "student":
        profile = _student_profile_for(db, user.id)
        if profile is not None and db.scalar(
            select(func.count()).where(GroupMember.student_id == profile.id)
        ):
            raise ConflictError("Remove this student from all groups before changing the role.")

    if new_role == "trainer" and _trainer_profile_for(db, user.id) is None:
        db.add(TrainerProfile(user_id=user.id))

    if new_role == "student":
        profile = _student_profile_for(db, user.id)
        if profile is None:
            if trainer_user_id is None:
                raise ValidationError("trainer_user_id is required to make this user a student.")
            db.add(
                StudentProfile(
                    user_id=user.id,
                    trainer_id=_resolve_trainer(db, trainer_user_id).id,
                )
            )
        elif trainer_user_id is not None:
            profile.trainer_id = _resolve_trainer(db, trainer_user_id).id

    user.role = new_role
    record_audit(db, ctx, "user.role_changed", "user", user.id, {"from": old_role, "to": new_role})
    _commit(db, "The role could not be changed.")

    return get_user_detail(db, user.id)


def change_status(db: Session, ctx: AdminContext, user_id: uuid.UUID, is_active: bool) -> dict:
    user = _get_user(db, user_id)

    if user.is_active == is_active:
        return get_user_detail(db, user.id)

    if user.id == ctx.actor.id:
        raise ConflictError("You cannot change the status of your own account.")

    if not is_active:
        if user.role == "admin":
            ensure_other_active_admin(db, user.id)
        # Sessions end at once: access tokens are rejected for inactive
        # users and refresh tokens are revoked here.
        revoke_all_refresh_tokens(db, user.id, datetime.now(timezone.utc))

    user.is_active = is_active
    record_audit(
        db, ctx,
        "user.activated" if is_active else "user.deactivated",
        "user", user.id,
    )
    _commit(db, "The status could not be changed.")

    return get_user_detail(db, user.id)


# ----- Groups --------------------------------------------------------------


def group_rows_stmt():
    member_counts = (
        select(GroupMember.group_id, func.count().label("n"))
        .group_by(GroupMember.group_id)
        .subquery()
    )
    return (
        select(
            Group,
            User.id.label("trainer_id"),
            User.full_name.label("trainer_name"),
            User.email.label("trainer_email"),
            func.coalesce(member_counts.c.n, 0).label("member_count"),
        )
        .join(TrainerProfile, TrainerProfile.id == Group.trainer_id)
        .join(User, User.id == TrainerProfile.user_id)
        .outerjoin(member_counts, member_counts.c.group_id == Group.id)
    )


def group_summary(row) -> dict:
    group = row.Group
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "is_active": group.is_active,
        "trainer": user_ref(row.trainer_id, row.trainer_name, row.trainer_email),
        "member_count": row.member_count,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


def list_groups(
    db: Session,
    params: PageParams,
    search: str | None = None,
    is_active: bool | None = None,
    trainer_user_id: uuid.UUID | None = None,
) -> dict:
    stmt = group_rows_stmt()

    if search and search.strip():
        pattern = like_pattern(search.strip())
        stmt = stmt.where(
            or_(
                Group.name.ilike(pattern, escape="\\"),
                User.full_name.ilike(pattern, escape="\\"),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Group.is_active.is_(is_active))
    if trainer_user_id:
        stmt = stmt.where(User.id == trainer_user_id)

    total = count_rows(db, stmt)
    rows = db.execute(
        stmt.order_by(Group.name, Group.id).offset(params.offset).limit(params.page_size)
    ).all()

    return build_page([group_summary(row) for row in rows], total, params)


def get_group_detail(db: Session, group_id: uuid.UUID) -> dict:
    row = db.execute(group_rows_stmt().where(Group.id == group_id)).first()

    if row is None:
        raise NotFoundError("Group not found.")

    members = db.execute(
        select(User, StudentProfile.level, StudentProfile.chess_rating, GroupMember.created_at)
        .join(StudentProfile, StudentProfile.id == GroupMember.student_id)
        .join(User, User.id == StudentProfile.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(User.full_name)
    ).all()

    return {
        **group_summary(row),
        "members": [
            {
                "id": member.User.id,
                "full_name": member.User.full_name,
                "email": member.User.email,
                "is_active": member.User.is_active,
                "level": member.level,
                "chess_rating": member.chess_rating,
                "joined_at": member.created_at,
            }
            for member in members
        ],
        "upcoming_session_count": db.scalar(
            select(func.count()).where(
                ClassSession.group_id == group_id,
                ClassSession.status == "scheduled",
                ClassSession.start_time > datetime.now(timezone.utc),
            )
        ),
        "assignment_count": db.scalar(
            select(func.count()).where(Assignment.group_id == group_id)
        ),
    }


def _get_group(db: Session, group_id: uuid.UUID) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise NotFoundError("Group not found.")
    return group


def _ensure_unique_group_name(
    db: Session,
    name: str,
    trainer_profile_id: uuid.UUID,
    exclude_id: uuid.UUID | None = None,
) -> None:
    stmt = select(Group.id).where(
        func.lower(Group.name) == name.lower(),
        Group.trainer_id == trainer_profile_id,
    )
    if exclude_id is not None:
        stmt = stmt.where(Group.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("This trainer already has a group with that name.")


def _add_members(db: Session, group: Group, student_user_ids: list[uuid.UUID]) -> list[str]:
    """Add students to a group in one batch, or fail without changing it."""
    rows = db.execute(
        select(User.id, User.role, User.full_name, StudentProfile.id.label("profile_id"))
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .where(User.id.in_(student_user_ids))
    ).all()
    found = {row.id: row for row in rows}

    missing = [str(i) for i in student_user_ids if i not in found]
    if missing:
        raise ValidationError(f"Unknown user IDs: {', '.join(missing)}.")

    not_students = [found[i].full_name for i in student_user_ids if found[i].role != "student"]
    if not_students:
        raise ValidationError(f"Not student accounts: {', '.join(not_students)}.")

    no_profile = [found[i].full_name for i in student_user_ids if found[i].profile_id is None]
    if no_profile:
        raise ValidationError(
            "These students need a profile with a trainer first: "
            f"{', '.join(no_profile)}."
        )

    profile_ids = {found[i].profile_id: found[i].full_name for i in student_user_ids}
    existing = db.scalars(
        select(GroupMember.student_id).where(
            GroupMember.group_id == group.id,
            GroupMember.student_id.in_(profile_ids),
        )
    ).all()
    if existing:
        names = ", ".join(sorted(profile_ids[i] for i in existing))
        raise ConflictError(f"Already members of this group: {names}.")

    db.add_all(GroupMember(group_id=group.id, student_id=pid) for pid in profile_ids)
    return [str(i) for i in student_user_ids]


def create_group(db: Session, ctx: AdminContext, data: dict) -> dict:
    trainer = _resolve_trainer(db, data["trainer_user_id"])
    _ensure_unique_group_name(db, data["name"], trainer.id)

    group = Group(
        name=data["name"],
        description=data.get("description"),
        is_active=data.get("is_active", True),
        trainer_id=trainer.id,
    )
    db.add(group)
    db.flush()

    added = _add_members(db, group, data["student_user_ids"]) if data.get("student_user_ids") else []

    record_audit(db, ctx, "group.created", "group", group.id, {"name": group.name, "students_added": len(added)})
    _commit(db, "The group could not be created because of a conflicting record.")

    return get_group_detail(db, group.id)


def update_group(db: Session, ctx: AdminContext, group_id: uuid.UUID, changes: dict) -> dict:
    group = _get_group(db, group_id)

    if "name" in changes:
        _ensure_unique_group_name(db, changes["name"], group.trainer_id, exclude_id=group.id)

    for field, value in changes.items():
        setattr(group, field, value)

    record_audit(db, ctx, "group.updated", "group", group.id, {"fields": sorted(changes)})
    _commit(db, "The group could not be updated.")

    return get_group_detail(db, group.id)


def assign_trainer(db: Session, ctx: AdminContext, group_id: uuid.UUID, trainer_user_id: uuid.UUID) -> dict:
    """Replace the group's trainer. Each group has exactly one trainer."""
    group = _get_group(db, group_id)
    trainer = _resolve_trainer(db, trainer_user_id)

    if trainer.id != group.trainer_id:
        _ensure_unique_group_name(db, group.name, trainer.id, exclude_id=group.id)
        previous = group.trainer_id
        group.trainer_id = trainer.id
        record_audit(
            db, ctx, "group.trainer_assigned", "group", group.id,
            {"from_trainer_profile": str(previous), "to_trainer_profile": str(trainer.id)},
        )
        _commit(db, "The trainer could not be assigned.")

    return get_group_detail(db, group.id)


def add_students(db: Session, ctx: AdminContext, group_id: uuid.UUID, student_user_ids: list[uuid.UUID]) -> dict:
    group = _get_group(db, group_id)
    added = _add_members(db, group, student_user_ids)

    record_audit(db, ctx, "group.students_added", "group", group.id, {"student_user_ids": added})
    _commit(db, "One or more students are already members of this group.")

    return get_group_detail(db, group.id)


def remove_student(db: Session, ctx: AdminContext, group_id: uuid.UUID, student_user_id: uuid.UUID) -> None:
    _get_group(db, group_id)

    membership = db.scalar(
        select(GroupMember)
        .join(StudentProfile, StudentProfile.id == GroupMember.student_id)
        .where(
            GroupMember.group_id == group_id,
            StudentProfile.user_id == student_user_id,
        )
    )
    if membership is None:
        raise NotFoundError("This student is not a member of the group.")

    db.delete(membership)
    record_audit(
        db, ctx, "group.student_removed", "group", group_id,
        {"student_user_id": str(student_user_id)},
    )
    db.commit()
