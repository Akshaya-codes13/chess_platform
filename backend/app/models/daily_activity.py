
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class DailyActivity(TimestampMixin, Base):
    __tablename__ = "daily_activity"

    __table_args__ = (
        UniqueConstraint("student_id", "activity_date", name="unique_student_activity_date"),
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

    activity_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    puzzles_attempted: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    puzzles_solved: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    games_played: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    xp_earned: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )
