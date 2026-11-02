
from datetime import date
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Date,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class StudentProfile(TimestampMixin, Base):
    __tablename__ = "student_profiles"

    __table_args__ = (
        CheckConstraint(
            "chess_rating >= 0",
            name="non_negative_rating",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    trainer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trainer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    date_of_birth: Mapped[date | None] = mapped_column(
    Date,
    nullable=True,
)

    chess_rating: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )

    level: Mapped[str] = mapped_column(
        String(30),
        default="beginner",
        server_default=text("'beginner'"),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
