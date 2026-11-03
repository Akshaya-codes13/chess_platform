"""Student module API.

Every route requires the ``student`` role and works only on the caller's own
records; see ``app.services.student_service`` for the visibility rules.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_student
from app.models import StudentProfile, User
from app.schemas.student import (
    AccessStatusResponse,
    AssignmentDetail,
    AssignmentProgress,
    AssignmentPuzzleItem,
    AssignmentSummary,
    AttemptRequest,
    AttemptResponse,
    AttendancePage,
    ActivityItem,
    BadgeItem,
    DashboardResponse,
    GamificationSummary,
    GroupDetail,
    GroupSummary,
    HintRequest,
    HintResponse,
    ProfileResponse,
    ProfileUpdate,
    ProgressSummary,
    PuzzleDetail,
    SessionDetail,
    SessionSummary,
)
from app.services import student_service
from app.utils.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/student", tags=["Student"])


def current_student(
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> StudentProfile:
    return student_service.require_student_profile(db, user)


# --- Dashboard and profile ---------------------------------------------------


@router.get("/access", response_model=AccessStatusResponse)
def access_status(
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return student_service.get_access_status(db, user)


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    user: User = Depends(require_student),
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.get_dashboard(db, user, student)


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return student_service.get_profile(db, user)


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(
    data: ProfileUpdate,
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return student_service.update_profile(
        db, user, data.model_dump(exclude_unset=True)
    )


# --- Groups ------------------------------------------------------------------


@router.get("/groups", response_model=Page[GroupSummary])
def list_groups(
    params: PageParams = Depends(page_params),
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.list_groups(db, student, params)


@router.get("/groups/{group_id}", response_model=GroupDetail)
def get_group(
    group_id: uuid.UUID,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.get_group(db, student, group_id)


# --- Assignments and puzzles -------------------------------------------------


@router.get("/assignments", response_model=Page[AssignmentSummary])
def list_assignments(
    status_filter: Literal["pending", "in_progress", "completed", "overdue"]
    | None = Query(None, alias="status"),
    params: PageParams = Depends(page_params),
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.list_assignments(db, student, params, status_filter)


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetail)
def get_assignment(
    assignment_id: uuid.UUID,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.get_assignment(db, student, assignment_id)


@router.post("/assignments/{assignment_id}/submit", response_model=AssignmentDetail)
def submit_assignment(
    assignment_id: uuid.UUID,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    """Hand in partial work, or resubmit after the trainer returned it.
    Completing every puzzle submits automatically."""
    return student_service.submit_assignment(db, student, assignment_id)


@router.get(
    "/assignments/{assignment_id}/progress", response_model=AssignmentProgress
)
def get_assignment_progress(
    assignment_id: uuid.UUID,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.get_assignment_progress(db, student, assignment_id)


@router.get(
    "/assignments/{assignment_id}/puzzles",
    response_model=list[AssignmentPuzzleItem],
)
def list_assignment_puzzles(
    assignment_id: uuid.UUID,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.list_assignment_puzzles(db, student, assignment_id)


@router.get("/puzzles/{puzzle_id}", response_model=PuzzleDetail)
def get_puzzle(
    puzzle_id: uuid.UUID,
    assignment_id: uuid.UUID = Query(...),
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    """Puzzle position and legal moves. The solution is never included
    until the student has solved the puzzle."""
    return student_service.get_puzzle(db, student, puzzle_id, assignment_id)


@router.post(
    "/puzzles/{puzzle_id}/attempts",
    response_model=AttemptResponse,
    status_code=status.HTTP_200_OK,
)
def submit_attempt(
    puzzle_id: uuid.UUID,
    data: AttemptRequest,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    """Validate the student's moves so far on the server.

    ``in_progress`` responses carry the opponent's reply and store nothing;
    ``solved`` and ``failed`` responses store one attempt.
    """
    return student_service.submit_attempt(
        db,
        student,
        puzzle_id,
        data.assignment_id,
        data.moves,
        data.time_taken_seconds,
        data.hints_used,
    )


@router.post("/puzzles/{puzzle_id}/hint", response_model=HintResponse)
def puzzle_hint(
    puzzle_id: uuid.UUID,
    data: HintRequest,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    """Level 1 names the piece to move; level 2 reveals the move. The moves
    so far must be a correct, unfinished prefix of the solution."""
    return student_service.get_hint(
        db, student, puzzle_id, data.assignment_id, data.moves, data.level
    )


# --- Sessions and attendance -------------------------------------------------


@router.get("/sessions", response_model=Page[SessionSummary])
def list_sessions(
    scope: Literal["upcoming", "past", "all"] = "all",
    params: PageParams = Depends(page_params),
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.list_sessions(db, student, params, scope)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: uuid.UUID,
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.get_session(db, student, session_id)


@router.get("/attendance", response_model=AttendancePage)
def list_attendance(
    params: PageParams = Depends(page_params),
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.list_attendance(db, student, params)


# --- Gamification and progress -----------------------------------------------


@router.get("/gamification", response_model=GamificationSummary)
def gamification(
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.get_gamification(db, student)


@router.get("/badges", response_model=list[BadgeItem])
def badges(
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.list_badges(db, student)


@router.get("/progress", response_model=ProgressSummary)
def progress(
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.get_progress(db, student)


@router.get("/activity", response_model=Page[ActivityItem])
def activity(
    params: PageParams = Depends(page_params),
    student: StudentProfile = Depends(current_student),
    db: Session = Depends(get_db),
):
    return student_service.list_activity(db, student, params)
