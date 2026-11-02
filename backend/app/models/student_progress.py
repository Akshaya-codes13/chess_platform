
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class StudentProgress(TimestampMixin, Base):
    __tablename__ = "student_progress"

    __table_args__ = (
        CheckConstraint("total_xp >= 0", name="non_negative_xp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    total_xp: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    current_streak: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    longest_streak: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    puzzles_solved: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    games_played: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )
