
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer,
    String, Uuid, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Game(TimestampMixin, Base):
    __tablename__ = "games"

    __table_args__ = (
        CheckConstraint("white_id != black_id", name="different_game_players"),
        CheckConstraint(
            "game_type IN ('assigned', 'simul', 'free')",
            name="valid_game_type",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'ongoing', 'completed', 'abandoned')",
            name="valid_game_status",
        ),
        CheckConstraint(
            "result IN ('white_win', 'black_win', 'draw', 'abandoned') OR result IS NULL",
            name="valid_game_result",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    white_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    black_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    game_type: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default="scheduled",
        server_default=text("'scheduled'"), nullable=False, index=True,
    )

    result: Mapped[str | None] = mapped_column(String(20), nullable=True)

    initial_fen: Mapped[str] = mapped_column(
        String(200), default="startpos",
        server_default=text("'startpos'"), nullable=False,
    )

    current_fen: Mapped[str | None] = mapped_column(String(200), nullable=True)

    moves: Mapped[list] = mapped_column(
        JSONB, default=list,
        server_default=text("'[]'::jsonb"), nullable=False,
    )

    time_control_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
