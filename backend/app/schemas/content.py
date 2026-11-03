import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PostType = Literal["article", "blog", "photo"]
PostStatus = Literal["draft", "published", "archived"]


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    type: PostType
    content: str | None = Field(default=None, max_length=50000)
    image_url: str | None = Field(default=None, max_length=500)


class PostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=200)
    type: PostType | None = None
    content: str | None = Field(default=None, max_length=50000)
    image_url: str | None = Field(default=None, max_length=500)


class PostSummary(BaseModel):
    id: uuid.UUID
    title: str
    type: str
    status: str
    image_url: str | None
    excerpt: str
    author_id: uuid.UUID
    author_name: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool


class PostDetail(PostSummary):
    content: str | None


class MediaUploadResponse(BaseModel):
    id: uuid.UUID
    url: str
    mime_type: str
    size_bytes: int
    original_name: str


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Required for students (one of their trainers); ignored for trainers,
    # whose feedback goes to the admin team.
    to_user_id: uuid.UUID | None = None
    message: str = Field(min_length=3, max_length=5000)
    category: Literal["teaching", "content", "platform", "scheduling", "other"] | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


class FeedbackReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str | None = Field(default=None, max_length=5000)


class FeedbackRecipient(BaseModel):
    id: uuid.UUID | None
    name: str


class FeedbackItem(BaseModel):
    id: uuid.UUID
    audience: str
    from_user_id: uuid.UUID
    from_name: str
    from_role: str
    to_user_id: uuid.UUID | None
    to_name: str | None
    message: str
    category: str | None
    rating: int | None
    status: str
    response: str | None
    reviewer_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    can_review: bool
