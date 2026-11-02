
import uuid

from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class PuzzleThemeMapping(TimestampMixin, Base):
    __tablename__ = "puzzle_theme_mappings"

    __table_args__ = (
        UniqueConstraint(
            "puzzle_id",
            "theme_id",
            name="unique_puzzle_theme",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    puzzle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("puzzles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    theme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("puzzle_themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
