"""Articles, blogs and gallery photos.

Permissions:

* Admins and trainers create posts. Students only read.
* The author, or any admin, edits, publishes, unpublishes, archives and
  deletes a post. Only drafts and archived posts can be deleted.
* Published posts are visible to every signed-in user. Drafts and archived
  posts are visible only to their author and admins; for anyone else they
  are reported as not found.
* A post's image must be an image uploaded to the platform (``/media/...``).
  Photo posts require one.
"""

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models import MediaFile, Post, User
from app.services import notification_service
from app.utils.pagination import PageParams, make_page, paginate

MEDIA_URL = re.compile(r"^/media/([0-9a-f]{32}\.(?:png|jpg|webp|gif))$")

TRANSITIONS = {
    "publish": ({"draft", "archived"}, "published"),
    "unpublish": ({"published"}, "draft"),
    "archive": ({"draft", "published"}, "archived"),
}


def _can_manage(user: User, post: Post) -> bool:
    return user.role == "admin" or post.author_id == user.id


def _visible(user: User):
    if user.role == "admin":
        return Post.id.is_not(None)
    return or_(Post.status == "published", Post.author_id == user.id)


def _item(post: Post, author_name: str, user: User, full: bool = False) -> dict:
    content = post.content or ""
    item = {
        "id": post.id,
        "title": post.title,
        "type": post.type,
        "status": post.status,
        "image_url": post.image_url,
        "excerpt": content[:240] + ("…" if len(content) > 240 else ""),
        "author_id": post.author_id,
        "author_name": author_name,
        "published_at": post.published_at,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "can_edit": _can_manage(user, post),
    }
    if full:
        item["content"] = post.content
    return item


def _check_image(db: Session, image_url: str | None) -> None:
    if image_url is None:
        return
    match = MEDIA_URL.match(image_url)
    if match is None or not db.scalar(select(MediaFile.id).where(MediaFile.storage_key == match.group(1))):
        raise ValidationError("Use an image uploaded to the platform.")


def _get(db: Session, user: User, post_id: uuid.UUID) -> Post:
    post = db.scalar(select(Post).where(Post.id == post_id, _visible(user)))
    if post is None:
        raise NotFoundError("Post not found.")
    return post


def _get_managed(db: Session, user: User, post_id: uuid.UUID) -> Post:
    post = _get(db, user, post_id)
    if not _can_manage(user, post):
        raise PermissionDeniedError("Only the author or an admin can change this post.")
    return post


def list_posts(
    db: Session,
    user: User,
    params: PageParams,
    *,
    post_type: str | None = None,
    status: str | None = None,
    mine: bool = False,
    search: str | None = None,
) -> dict:
    query = select(Post, User.full_name).join(User, User.id == Post.author_id).where(_visible(user))

    if post_type:
        query = query.where(Post.type == post_type)
    if status:
        query = query.where(Post.status == status)
    if mine:
        query = query.where(Post.author_id == user.id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))

    query = query.order_by(Post.published_at.desc().nulls_last(), Post.created_at.desc(), Post.id)
    rows, total = paginate(db, query, params)
    return make_page([_item(post, name, user) for post, name in rows], total, params)


def get_post(db: Session, user: User, post_id: uuid.UUID) -> dict:
    post = _get(db, user, post_id)
    author = db.scalar(select(User.full_name).where(User.id == post.author_id))
    return _item(post, author, user, full=True)


def create_post(db: Session, user: User, data: dict) -> dict:
    _check_image(db, data.get("image_url"))
    if data["type"] == "photo" and not data.get("image_url"):
        raise ValidationError("A photo post needs an image.")

    post = Post(
        author_id=user.id,
        title=data["title"].strip(),
        content=data.get("content"),
        type=data["type"],
        image_url=data.get("image_url"),
        status="draft",
    )
    db.add(post)
    db.commit()
    return get_post(db, user, post.id)


def update_post(db: Session, user: User, post_id: uuid.UUID, changes: dict) -> dict:
    post = _get_managed(db, user, post_id)

    if "image_url" in changes:
        _check_image(db, changes["image_url"])
        post.image_url = changes["image_url"]
    if changes.get("title"):
        post.title = changes["title"].strip()
    if "content" in changes:
        post.content = changes["content"]
    if changes.get("type"):
        post.type = changes["type"]

    if post.type == "photo" and not post.image_url:
        raise ValidationError("A photo post needs an image.")

    db.commit()
    return get_post(db, user, post.id)


def change_status(db: Session, user: User, post_id: uuid.UUID, action: str) -> dict:
    post = _get_managed(db, user, post_id)
    allowed, new_status = TRANSITIONS[action]

    if post.status not in allowed:
        raise ConflictError(f"Cannot {action} a post that is {post.status}.")

    post.status = new_status

    if action == "publish":
        first_publication = post.published_at is None
        post.published_at = post.published_at or datetime.now(timezone.utc)

        if first_publication:
            readers = db.scalars(
                select(User.id).where(User.is_active.is_(True), User.id != post.author_id)
            ).all()
            notification_service.notify(
                db,
                readers,
                "post_published",
                f"New {post.type}: {post.title}",
                f"{user.full_name} published “{post.title}”.",
                {"post_id": post.id},
            )

    db.commit()
    return get_post(db, user, post.id)


def delete_post(db: Session, user: User, post_id: uuid.UUID) -> None:
    post = _get_managed(db, user, post_id)

    if post.status == "published":
        raise ConflictError("Unpublish or archive the post before deleting it.")

    db.delete(post)
    db.commit()
