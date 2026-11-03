
import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Integer, String, Text, Uuid, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class GameDatabase(TimestampMixin, Base):
    """A named collection of PGN games owned by one user.

    Shared databases (``is_shared``) are readable by every signed-in user;
    only the owner (or an admin) can change them.
    """

    __tablename__ = "game_databases"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_shared: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False,
    )


class GameFolder(TimestampMixin, Base):
    """A folder inside a game database; folders nest through ``parent_id``."""

    __tablename__ = "game_folders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    database_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("game_databases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("game_folders.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)


class PgnGame(TimestampMixin, Base):
    """One game imported from PGN, with its headers and SAN move list."""

    __tablename__ = "pgn_games"

    __table_args__ = (
        CheckConstraint(
            "result IN ('1-0', '0-1', '1/2-1/2', '*')",
            name="valid_pgn_result",
        ),
        CheckConstraint("ply_count >= 0", name="non_negative_ply_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    database_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("game_databases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("game_folders.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    white: Mapped[str] = mapped_column(String(150), nullable=False)
    black: Mapped[str] = mapped_column(String(150), nullable=False)
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    event: Mapped[str | None] = mapped_column(String(200), nullable=True)
    site: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # PGN dates may be partial ("2024.??.??"), so they are kept as text.
    game_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    round: Mapped[str | None] = mapped_column(String(20), nullable=True)
    eco: Mapped[str | None] = mapped_column(String(10), nullable=True)
    white_elo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    black_elo: Mapped[int | None] = mapped_column(Integer, nullable=True)

    initial_fen: Mapped[str | None] = mapped_column(String(200), nullable=True)

    moves: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False,
    )

    ply_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )

    headers: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False,
    )

    pgn: Mapped[str] = mapped_column(Text, nullable=False)
