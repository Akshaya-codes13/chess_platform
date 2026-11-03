"""The signed-in user's in-app notifications."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.account import MarkedCount, NotificationItem, NotificationPage, UnreadCount
from app.services import notification_service
from app.utils.pagination import PageParams, page_params

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationPage)
def list_notifications(
    unread_only: bool = False,
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.list_notifications(db, user, params, unread_only)


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"unread": notification_service.unread_count(db, user)}


@router.post("/read-all", response_model=MarkedCount)
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"marked": notification_service.mark_all_read(db, user)}


@router.post("/{notification_id}/read", response_model=NotificationItem)
def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.mark_read(db, user, notification_id)
