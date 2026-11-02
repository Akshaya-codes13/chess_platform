
import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class AssignmentPuzzle(TimestampMixin, Base):
    __tablename__ = "assignment_puzzles"

    __table_args__ = (
        UniqueConstraint("assignment_id", "puzzle_id", name="unique_assignment_puzzle"),
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

    puzzle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("puzzles.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    points: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False,
    )

    display_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )
