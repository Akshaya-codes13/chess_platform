
import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class XPEvent(TimestampMixin, Base):
    __tablename__ = "xp_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    points: Mapped[int] = mapped_column(Integer, nullable=False)

    reason: Mapped[str] = mapped_column(String(200), nullable=False)

    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
