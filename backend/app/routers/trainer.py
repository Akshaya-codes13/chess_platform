import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_trainer
from app.models import TrainerProfile, User
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentDetail,
    AssignmentProgress,
    AssignmentSummary,
    AssignmentUpdate,
    StudentSubmission,
    SubmissionReview,
)
from app.schemas.puzzle import (
    PuzzleCreate,
    PuzzleDetail,
    PuzzleDifficulty,
    PuzzleStatus,
    PuzzleSummary,
    PuzzleUpdate,
    PuzzleValidateRequest,
    PuzzleValidateResponse,
    TaxonomyResponse,
)
from app.schemas.session import (
    AttendanceRequest,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    SessionUpdate,
)
from app.schemas.trainer import (
    DashboardResponse,
    GroupDetail,
    GroupPerformance,
    GroupStudent,
    GroupSummary,
    StudentPerformance,
    TrainerProfileResponse,
    TrainerProfileUpdate,
)
from app.services import (
    assignment_service,
    puzzle_service,
    session_service,
    trainer_service,
)
from app.services.trainer_access import get_trainer_profile
from app.utils.pagination import Page, PageParams, page_params

# Trainer-only: admins manage groups through the Admin module, and
# students have their own routes, so both get 403 here.
router = APIRouter(
    prefix="/trainer",
    tags=["Trainer"],
)


def current_trainer(
    user: User = Depends(require_trainer),
    db: Session = Depends(get_db),
) -> TrainerProfile:
    return get_trainer_profile(db, user)


# Dashboard and profile

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Summary of the trainer's groups, schedule, assignments and activity."""
    return trainer_service.dashboard(db, trainer)


@router.get("/profile", response_model=TrainerProfileResponse)
def get_profile(
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return trainer_service.profile_response(db, trainer)


@router.patch("/profile", response_model=TrainerProfileResponse)
def update_profile(
    data: TrainerProfileUpdate,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Update permitted profile fields; role and account status are rejected."""
    return trainer_service.update_profile(db, trainer, data.model_dump(exclude_unset=True))


# Groups and students

@router.get("/groups", response_model=Page[GroupSummary])
def list_groups(
    search: str | None = Query(None, max_length=100),
    is_active: bool | None = None,
    params: PageParams = Depends(page_params),
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Groups an administrator has assigned to this trainer."""
    return trainer_service.list_groups(db, trainer, params, search=search, is_active=is_active)


@router.get("/groups/{group_id}", response_model=GroupDetail)
def get_group(
    group_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return trainer_service.get_group(db, trainer, group_id)


@router.get("/groups/{group_id}/students", response_model=Page[GroupStudent])
def list_group_students(
    group_id: uuid.UUID,
    search: str | None = Query(None, max_length=100),
    sort: Literal["name", "-name", "rating", "-rating", "joined", "-joined"] = "name",
    params: PageParams = Depends(page_params),
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return trainer_service.list_group_students(
        db, trainer, group_id, params, search=search, sort=sort
    )


@router.get("/groups/{group_id}/assignments", response_model=Page[AssignmentSummary])
def list_group_assignments(
    group_id: uuid.UUID,
    params: PageParams = Depends(page_params),
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Assignment history of one group."""
    return assignment_service.list_assignments(db, trainer, params, group_id=group_id)


@router.get("/groups/{group_id}/performance", response_model=GroupPerformance)
def get_group_performance(
    group_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return trainer_service.group_performance(db, trainer, group_id)


@router.get("/students/{student_id}/performance", response_model=StudentPerformance)
def get_student_performance(
    student_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Profile and progress of a student in one of the trainer's groups."""
    return trainer_service.student_performance(db, trainer, student_id)


# Puzzles

@router.get("/puzzle-taxonomy", response_model=TaxonomyResponse)
def get_puzzle_taxonomy(
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return puzzle_service.get_taxonomy(db)


@router.post("/puzzles/validate", response_model=PuzzleValidateResponse)
def validate_puzzle(
    data: PuzzleValidateRequest,
    trainer: TrainerProfile = Depends(current_trainer),
):
    """Check a FEN and UCI solution without saving anything."""
    return puzzle_service.validate_position(data.fen, data.solution)


@router.get("/puzzles", response_model=Page[PuzzleSummary])
def list_puzzles(
    search: str | None = Query(None, max_length=100),
    difficulty: PuzzleDifficulty | None = None,
    category_id: uuid.UUID | None = None,
    theme_id: uuid.UUID | None = None,
    rating_min: int | None = Query(None, ge=0, le=4000),
    rating_max: int | None = Query(None, ge=0, le=4000),
    status: PuzzleStatus | None = None,
    ownership: Literal["all", "mine", "library"] = "all",
    sort: Literal["-created_at", "created_at", "rating", "-rating"] = "-created_at",
    params: PageParams = Depends(page_params),
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Published puzzles plus the trainer's own puzzles in any status."""
    return puzzle_service.list_puzzles(
        db, trainer, params,
        search=search, difficulty=difficulty, category_id=category_id,
        theme_id=theme_id, rating_min=rating_min, rating_max=rating_max,
        status=status, ownership=ownership, sort=sort,
    )


@router.post("/puzzles", response_model=PuzzleDetail, status_code=201)
def create_puzzle(
    data: PuzzleCreate,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Create a draft puzzle after validating the FEN and every solution move."""
    return puzzle_service.create_puzzle(db, trainer, data.model_dump())


@router.get("/puzzles/{puzzle_id}", response_model=PuzzleDetail)
def get_puzzle(
    puzzle_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return puzzle_service.get_puzzle(db, trainer, puzzle_id)


@router.patch("/puzzles/{puzzle_id}", response_model=PuzzleDetail)
def update_puzzle(
    puzzle_id: uuid.UUID,
    data: PuzzleUpdate,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return puzzle_service.update_puzzle(db, trainer, puzzle_id, data.model_dump(exclude_unset=True))


@router.post("/puzzles/{puzzle_id}/{action}", response_model=PuzzleDetail)
def change_puzzle_status(
    puzzle_id: uuid.UUID,
    action: Literal["publish", "unpublish", "archive", "restore"],
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return puzzle_service.change_puzzle_status(db, trainer, puzzle_id, action)


# Assignments

@router.get("/assignments", response_model=Page[AssignmentSummary])
def list_assignments(
    status: Literal["draft", "published", "completed", "cancelled"] | None = None,
    group_id: uuid.UUID | None = None,
    search: str | None = Query(None, max_length=100),
    sort: Literal["-created_at", "created_at", "due_date", "-due_date", "title"] = "-created_at",
    params: PageParams = Depends(page_params),
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return assignment_service.list_assignments(
        db, trainer, params, status=status, group_id=group_id, search=search, sort=sort
    )


@router.post("/assignments", response_model=AssignmentDetail, status_code=201)
def create_assignment(
    data: AssignmentCreate,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Create a draft, or publish immediately with ``publish: true``."""
    return assignment_service.create_assignment(db, trainer, data.model_dump())


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetail)
def get_assignment(
    assignment_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return assignment_service.get_assignment(db, trainer, assignment_id)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentDetail)
def update_assignment(
    assignment_id: uuid.UUID,
    data: AssignmentUpdate,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Edit a draft assignment."""
    return assignment_service.update_assignment(
        db, trainer, assignment_id, data.model_dump(exclude_unset=True)
    )


@router.get("/assignments/{assignment_id}/progress", response_model=AssignmentProgress)
def get_assignment_progress(
    assignment_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return assignment_service.assignment_progress(db, trainer, assignment_id)


@router.get(
    "/assignments/{assignment_id}/submissions/{student_id}",
    response_model=StudentSubmission,
)
def get_student_submission(
    assignment_id: uuid.UUID,
    student_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """A recipient's attempts (moves, hints, time) and submission."""
    return assignment_service.get_student_submission(db, trainer, assignment_id, student_id)


@router.post(
    "/assignments/{assignment_id}/submissions/{student_id}/review",
    response_model=StudentSubmission,
)
def review_submission(
    assignment_id: uuid.UUID,
    student_id: uuid.UUID,
    data: SubmissionReview,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Grade or return the latest submission; the student is notified."""
    return assignment_service.review_submission(
        db, trainer, assignment_id, student_id, data.model_dump()
    )


@router.post("/assignments/{assignment_id}/{action}", response_model=AssignmentDetail)
def change_assignment_status(
    assignment_id: uuid.UUID,
    action: Literal["publish", "close", "cancel"],
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return assignment_service.change_assignment_status(db, trainer, assignment_id, action)


# Sessions and attendance

@router.get("/sessions", response_model=Page[SessionSummary])
def list_sessions(
    scope: Literal["all", "upcoming", "past", "active", "completed"] = "all",
    status: Literal["scheduled", "ongoing", "completed", "cancelled"] | None = None,
    group_id: uuid.UUID | None = None,
    search: str | None = Query(None, max_length=100),
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
    params: PageParams = Depends(page_params),
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return session_service.list_sessions(
        db, trainer, params,
        scope=scope, status=status, group_id=group_id, search=search,
        starts_after=starts_after, starts_before=starts_before,
    )


@router.post("/sessions", response_model=SessionDetail, status_code=201)
def create_session(
    data: SessionCreate,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return session_service.create_session(db, trainer, data.model_dump())


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: uuid.UUID,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Session details with the roster and recorded attendance."""
    return session_service.get_session(db, trainer, session_id)


@router.patch("/sessions/{session_id}", response_model=SessionDetail)
def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return session_service.update_session(db, trainer, session_id, data.model_dump(exclude_unset=True))


@router.post("/sessions/{session_id}/attendance", response_model=SessionDetail)
def record_attendance(
    session_id: uuid.UUID,
    data: AttendanceRequest,
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    """Record or update attendance; one record per student per session."""
    return session_service.record_attendance(
        db, trainer, session_id, [record.model_dump() for record in data.records]
    )


@router.post("/sessions/{session_id}/{action}", response_model=SessionDetail)
def change_session_status(
    session_id: uuid.UUID,
    action: Literal["cancel", "complete"],
    trainer: TrainerProfile = Depends(current_trainer),
    db: Session = Depends(get_db),
):
    return session_service.change_session_status(db, trainer, session_id, action)
