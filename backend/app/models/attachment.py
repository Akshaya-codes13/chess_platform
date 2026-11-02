
import uuid

from sqlalchemy import ForeignKey, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)

    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)

    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    file_size: Mapped[int | None] = mapped_column(nullable=True)
