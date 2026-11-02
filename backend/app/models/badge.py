
import uuid

from sqlalchemy import Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Badge(TimestampMixin, Base):
    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    xp_reward: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False,
    )
