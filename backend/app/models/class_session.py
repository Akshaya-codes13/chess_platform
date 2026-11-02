
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class ClassSession(TimestampMixin, Base):
    __tablename__ = "class_sessions"

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="valid_session_time",
        ),
        CheckConstraint(
            "session_type IN ('individual', 'group')",
            name="valid_session_type",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'ongoing', 'completed', 'cancelled')",
            name="valid_session_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    trainer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trainer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    session_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="scheduled",
        server_default=text("'scheduled'"),
        nullable=False,
        index=True,
    )

    meeting_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
