
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, ForeignKey, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class StudentBadge(TimestampMixin, Base):
    __tablename__ = "student_badges"

    __table_args__ = (
        UniqueConstraint("student_id", "badge_id", name="unique_student_badge"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    badge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("badges.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
