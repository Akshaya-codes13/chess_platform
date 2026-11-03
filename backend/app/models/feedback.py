
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Feedback(TimestampMixin, Base):
    """Feedback from a student to a trainer, or from a trainer to the admins.

    Trainer-addressed feedback names the trainer in ``to_user_id``. Feedback
    for the admins has ``audience = 'admin'`` and no single recipient: every
    admin sees it.
    """

    __tablename__ = "feedback"

    __table_args__ = (
        CheckConstraint(
            "audience IN ('trainer', 'admin')",
            name="valid_feedback_audience",
        ),
        CheckConstraint(
            "audience = 'admin' OR to_user_id IS NOT NULL",
            name="trainer_feedback_has_recipient",
        ),
        CheckConstraint(
            "status IN ('open', 'reviewed')",
            name="valid_feedback_status",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="valid_feedback_rating",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    from_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    audience: Mapped[str] = mapped_column(
        String(20), default="trainer",
        server_default=text("'trainer'"), nullable=False, index=True,
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="open",
        server_default=text("'open'"), nullable=False, index=True,
    )

    response: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
