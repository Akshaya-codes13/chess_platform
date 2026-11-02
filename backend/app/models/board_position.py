
import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class BoardPosition(TimestampMixin, Base):
    __tablename__ = "board_positions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    fen: Mapped[str] = mapped_column(String(200), nullable=False)

    move_number: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    label: Mapped[str | None] = mapped_column(String(150), nullable=True)

    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
