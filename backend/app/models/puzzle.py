
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Puzzle(TimestampMixin, Base):
    __tablename__ = "puzzles"

    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR rating >= 0",
            name="non_negative_rating",
        ),
        CheckConstraint(
            "type IN ('puzzle', 'study', 'composition')",
            name="valid_puzzle_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="valid_puzzle_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("puzzle_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # NULL for library puzzles (seeded or imported); set for puzzles a
    # trainer authored, who is then the only trainer allowed to edit them.
    created_by_trainer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trainer_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    lichess_id: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
    )

    fen: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    solution: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    rating_deviation: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    popularity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        server_default=text("'manual'"),
        nullable=False,
    )

    type: Mapped[str] = mapped_column(
        String(20),
        default="puzzle",
        server_default=text("'puzzle'"),
        nullable=False,
    )

    difficulty: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="published",
        server_default=text("'published'"),
        nullable=False,
        index=True,
    )
