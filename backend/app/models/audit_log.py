
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)

    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    details: Mapped[dict] = mapped_column(
        JSONB, default=dict,
        server_default=text("'{}'::jsonb"), nullable=False,
    )

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
