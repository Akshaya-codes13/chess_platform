"""Articles, blogs, gallery photos and image uploads; see content_service."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.errors import NotFoundError
from app.models import User
from app.schemas.content import (
    MediaUploadResponse,
    PostCreate,
    PostDetail,
    PostStatus,
    PostSummary,
    PostType,
    PostUpdate,
)
from app.services import content_service, media_service
from app.services.storage import KEY_PATTERN
from app.utils.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/content", tags=["Content"])
media_router = APIRouter(tags=["Content"])

require_author = require_roles("admin", "trainer")


@router.get("/posts", response_model=Page[PostSummary])
def list_posts(
    type: PostType | None = None,
    status: PostStatus | None = None,
    mine: bool = False,
    search: str | None = Query(None, max_length=100),
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Published posts, plus the caller's own drafts (admins see all)."""
    return content_service.list_posts(
        db, user, params, post_type=type, status=status, mine=mine, search=search
    )


@router.post("/posts", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
def create_post(data: PostCreate, user: User = Depends(require_author), db: Session = Depends(get_db)):
    """New posts start as drafts."""
    return content_service.create_post(db, user, data.model_dump())


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post(post_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return content_service.get_post(db, user, post_id)


@router.patch("/posts/{post_id}", response_model=PostDetail)
def update_post(
    post_id: uuid.UUID,
    data: PostUpdate,
    user: User = Depends(require_author),
    db: Session = Depends(get_db),
):
    return content_service.update_post(db, user, post_id, data.model_dump(exclude_unset=True))


@router.post("/posts/{post_id}/{action}", response_model=PostDetail)
def change_post_status(
    post_id: uuid.UUID,
    action: Literal["publish", "unpublish", "archive"],
    user: User = Depends(require_author),
    db: Session = Depends(get_db),
):
    return content_service.change_status(db, user, post_id, action)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: uuid.UUID, user: User = Depends(require_author), db: Session = Depends(get_db)):
    content_service.delete_post(db, user, post_id)


@router.post("/media", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    user: User = Depends(require_author),
    db: Session = Depends(get_db),
):
    """Upload a PNG, JPEG, WebP or GIF image (max 5 MB)."""
    data = await file.read(settings.media_max_bytes + 1)
    return media_service.upload_image(db, user, file.filename or "image", data)


@media_router.get("/media/{key}", include_in_schema=False)
def serve_media(key: str, db: Session = Depends(get_db)):
    """Serve an uploaded image. Keys are random and unguessable."""
    if not KEY_PATTERN.match(key):
        raise NotFoundError("File not found.")

    found = media_service.read_media(db, key)
    if found is None:
        raise NotFoundError("File not found.")

    data, mime = found
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
