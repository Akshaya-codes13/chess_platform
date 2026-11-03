"""Feedback between students, trainers and admins; see feedback_service."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.content import FeedbackCreate, FeedbackItem, FeedbackRecipient, FeedbackReview
from app.services import feedback_service
from app.utils.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.get("/recipients", response_model=list[FeedbackRecipient])
def recipients(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Who the caller can send feedback to."""
    return feedback_service.recipients(db, user)


@router.get("", response_model=Page[FeedbackItem])
def list_feedback(
    box: Literal["inbox", "sent", "all"] = "inbox",
    status: Literal["open", "reviewed"] | None = None,
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return feedback_service.list_feedback(db, user, params, box, status)


@router.post("", response_model=FeedbackItem, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    data: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return feedback_service.submit(db, user, data.model_dump())


@router.get("/{feedback_id}", response_model=FeedbackItem)
def get_feedback(
    feedback_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return feedback_service.get_feedback(db, user, feedback_id)


@router.post("/{feedback_id}/review", response_model=FeedbackItem)
def review_feedback(
    feedback_id: uuid.UUID,
    data: FeedbackReview,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return feedback_service.review(db, user, feedback_id, data.response)
