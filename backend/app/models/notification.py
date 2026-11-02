
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)

    is_read: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    data: Mapped[dict] = mapped_column(
        JSONB, default=dict,
        server_default=text("'{}'::jsonb"), nullable=False,
    )
