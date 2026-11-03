"""Ownership rules shared by the Trainer module services.

A trainer owns the groups whose ``trainer_id`` is their trainer profile
(assigned by an Admin). They may see a student only while that student is a
member of one of those groups. Resources of other trainers are reported as
"not found" so their existence is not revealed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models import Group, GroupMember, StudentProfile, TrainerProfile, User


def like_pattern(term: str) -> str:
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def get_trainer_profile(db: Session, user: User) -> TrainerProfile:
    profile = db.scalar(
        select(TrainerProfile).where(TrainerProfile.user_id == user.id)
    )

    if profile is None:
        raise PermissionDeniedError(
            "No trainer profile is linked to this account. Ask an administrator to set one up."
        )

    return profile


def owned_group_ids(trainer: TrainerProfile):
    return select(Group.id).where(Group.trainer_id == trainer.id)


def accessible_student_ids(trainer: TrainerProfile):
    """Students who belong to at least one of the trainer's groups."""
    return (
        select(GroupMember.student_id)
        .join(Group, Group.id == GroupMember.group_id)
        .where(Group.trainer_id == trainer.id)
    )


def get_owned_group(db: Session, trainer: TrainerProfile, group_id: uuid.UUID) -> Group:
    group = db.get(Group, group_id)

    if group is None or group.trainer_id != trainer.id:
        raise NotFoundError("Group not found.")

    return group


def get_active_owned_group(db: Session, trainer: TrainerProfile, group_id: uuid.UUID) -> Group:
    group = get_owned_group(db, trainer, group_id)

    if not group.is_active:
        raise ConflictError("This group is inactive.")

    return group


def get_accessible_student(
    db: Session, trainer: TrainerProfile, student_id: uuid.UUID
) -> StudentProfile:
    student = db.scalar(
        select(StudentProfile).where(
            StudentProfile.id == student_id,
            StudentProfile.id.in_(accessible_student_ids(trainer)),
        )
    )

    if student is None:
        raise NotFoundError("Student not found.")

    return student


def group_member_ids(db: Session, group_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.scalars(select(GroupMember.student_id).where(GroupMember.group_id == group_id))
    )
