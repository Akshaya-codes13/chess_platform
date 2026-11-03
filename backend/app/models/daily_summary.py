
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


def _counter() -> Mapped[int]:
    return mapped_column(Integer, default=0, server_default=text("0"), nullable=False)


class DailyPlatformSummary(TimestampMixin, Base):
    """Academy-wide totals for one UTC day, written by the daily summary job."""

    __tablename__ = "daily_platform_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    summary_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)

    new_students: Mapped[int] = _counter()
    new_trainers: Mapped[int] = _counter()
    active_students: Mapped[int] = _counter()
    sessions_held: Mapped[int] = _counter()
    attendance_present: Mapped[int] = _counter()
    attendance_late: Mapped[int] = _counter()
    attendance_absent: Mapped[int] = _counter()
    attendance_excused: Mapped[int] = _counter()
    submissions: Mapped[int] = _counter()
    puzzle_attempts: Mapped[int] = _counter()
    puzzles_solved: Mapped[int] = _counter()
    xp_awarded: Mapped[int] = _counter()

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class DailyTrainerSummary(TimestampMixin, Base):
    """Per-trainer totals for one UTC day, written by the daily summary job."""

    __tablename__ = "daily_trainer_summaries"

    __table_args__ = (
        UniqueConstraint("trainer_id", "summary_date", name="unique_trainer_summary_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    trainer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trainer_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    sessions_held: Mapped[int] = _counter()
    attendance_present: Mapped[int] = _counter()
    attendance_late: Mapped[int] = _counter()
    attendance_absent: Mapped[int] = _counter()
    attendance_excused: Mapped[int] = _counter()
    submissions: Mapped[int] = _counter()
    active_students: Mapped[int] = _counter()
    puzzle_attempts: Mapped[int] = _counter()
    puzzles_solved: Mapped[int] = _counter()

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
