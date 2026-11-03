"""Image uploads for posts and the gallery.

The file type is decided by the file's first bytes, not by its name or the
client's Content-Type, and only raster images are accepted (no SVG, which
could carry scripts). Stored keys are random, so media URLs cannot be
guessed; they are served without authentication so ``<img>`` tags work.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationError
from app.models import MediaFile, User
from app.services.storage import get_storage

# (magic prefix, extension, mime type)
SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"GIF87a", "gif", "image/gif"),
    (b"GIF89a", "gif", "image/gif"),
)


def detect_image(data: bytes) -> tuple[str, str] | None:
    for prefix, extension, mime in SIGNATURES:
        if data.startswith(prefix):
            return extension, mime
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def media_url(key: str) -> str:
    return f"/media/{key}"


def upload_image(db: Session, user: User, file_name: str, data: bytes) -> dict:
    if not data:
        raise ValidationError("The file is empty.")
    if len(data) > settings.media_max_bytes:
        raise ValidationError(f"Images can be at most {settings.media_max_bytes // (1024 * 1024)} MB.")

    detected = detect_image(data)
    if detected is None:
        raise ValidationError("Only PNG, JPEG, WebP and GIF images can be uploaded.")

    extension, mime = detected
    key = f"{uuid.uuid4().hex}.{extension}"
    get_storage().save(key, data)

    media = MediaFile(
        uploaded_by=user.id,
        storage_key=key,
        original_name=(file_name or "image")[:255],
        mime_type=mime,
        size_bytes=len(data),
    )
    db.add(media)
    db.commit()

    return {
        "id": media.id,
        "url": media_url(key),
        "mime_type": mime,
        "size_bytes": len(data),
        "original_name": media.original_name,
    }


def read_media(db: Session, key: str) -> tuple[bytes, str] | None:
    mime = db.scalar(select(MediaFile.mime_type).where(MediaFile.storage_key == key))
    if mime is None:
        return None
    data = get_storage().open(key)
    return (data, mime) if data is not None else None
