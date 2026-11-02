
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "student_id", "attempt_number",
            name="unique_assignment_attempt",
        ),
        CheckConstraint("attempt_number >= 1", name="positive_attempt_number"),
        CheckConstraint("score IS NULL OR score >= 0", name="non_negative_score"),
        CheckConstraint(
            "status IN ('submitted', 'graded', 'returned')",
            name="valid_submission_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="submitted",
        server_default=text("'submitted'"), nullable=False, index=True,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    trainer_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
