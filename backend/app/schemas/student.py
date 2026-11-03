import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.pagination import Page

UCI_MOVE_PATTERN = r"^[a-h][1-8][a-h][1-8][qrbn]?$"


# --- Shared pieces -----------------------------------------------------------


class TrainerSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    specialization: str | None = None
    bio: str | None = None
    experience_years: int


class PositionState(BaseModel):
    fen: str
    turn: str
    legal_moves: list[str]
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool


class SubmissionInfo(BaseModel):
    attempt_number: int
    status: str
    score: int | None = None
    submitted_at: datetime
    trainer_feedback: str | None = None


class AssignmentProgress(BaseModel):
    total_puzzles: int
    completed_puzzles: int
    remaining_puzzles: int
    completion_percent: float
    total_points: int
    earned_points: int
    attempts: int
    last_attempt_at: datetime | None = None


class BadgeItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    icon_url: str | None = None
    xp_reward: int
    earned: bool
    earned_at: datetime | None = None


class XPEventItem(BaseModel):
    id: uuid.UUID
    points: int
    reason: str
    source_type: str | None = None
    created_at: datetime


class Milestone(BaseModel):
    badge_code: str
    badge_name: str
    description: str | None = None
    counter: str
    current: int
    target: int


# --- Profile -----------------------------------------------------------------


class AccountInfo(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None = None
    avatar_url: str | None = None
    language: str
    role: str
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class StudentInfo(BaseModel):
    date_of_birth: date | None = None
    chess_rating: int
    level: str
    joined_at: datetime


class GroupMembershipItem(BaseModel):
    id: uuid.UUID
    name: str
    trainer_name: str


class AccessStatusResponse(BaseModel):
    """Whether the student portal is usable yet.

    Self-registered students have no student profile until an administrator
    assigns them a trainer; until then the status is ``awaiting_trainer``.
    """

    status: Literal["ready", "awaiting_trainer"]
    trainer: TrainerSummary | None = None


class ProfileResponse(BaseModel):
    account: AccountInfo
    student: StudentInfo | None = None
    trainer: TrainerSummary | None = None
    groups: list[GroupMembershipItem]


class ProfileUpdate(BaseModel):
    """Fields a student may change. Anything else is rejected with 422."""

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(
        default=None, max_length=20, pattern=r"^\+?[0-9][0-9 ()-]{5,19}$"
    )
    avatar_url: str | None = Field(
        default=None, max_length=500, pattern=r"^https?://\S+$"
    )
    language: str | None = Field(
        default=None, max_length=10, pattern=r"^[a-z]{2}(-[A-Z]{2})?$"
    )
    date_of_birth: date | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, value):
        if value is not None and len(value.strip()) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return value.strip() if value else value

    @field_validator("date_of_birth")
    @classmethod
    def plausible_birth_date(cls, value):
        if value is not None and not date(1900, 1, 1) <= value <= date.today():
            raise ValueError("Date of birth must be between 1900 and today.")
        return value


# --- Groups and sessions -----------------------------------------------------


class SessionSummary(BaseModel):
    id: uuid.UUID
    title: str
    session_type: str
    status: str
    start_time: datetime
    end_time: datetime
    group_id: uuid.UUID | None = None
    group_name: str | None = None
    trainer_name: str
    attendance_status: str | None = None
    is_upcoming: bool


class SessionDetail(SessionSummary):
    description: str | None = None
    meeting_url: str | None = None
    attendance_remarks: str | None = None


class AttendanceItem(BaseModel):
    session_id: uuid.UUID
    session_title: str
    session_status: str
    start_time: datetime
    end_time: datetime
    trainer_name: str
    group_name: str | None = None
    status: str
    remarks: str | None = None


class AttendanceSummary(BaseModel):
    total: int
    present: int
    late: int
    absent: int
    excused: int
    scheduled: int
    attendance_rate_percent: float | None = None


class AttendancePage(Page[AttendanceItem]):
    summary: AttendanceSummary


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    trainer: TrainerSummary
    member_count: int
    joined_at: datetime
    upcoming_session_count: int


# --- Assignments and puzzles -------------------------------------------------


class AssignmentSummary(BaseModel):
    id: uuid.UUID
    title: str
    assignment_type: str
    status: str
    is_closed: bool
    due_date: datetime | None = None
    published_at: datetime | None = None
    group_id: uuid.UUID | None = None
    group_name: str | None = None
    trainer_name: str
    progress: AssignmentProgress
    submission: SubmissionInfo | None = None


class AssignmentPuzzleItem(BaseModel):
    puzzle_id: uuid.UUID
    display_order: int
    points: int
    rating: int | None = None
    difficulty: str | None = None
    themes: list[str]
    status: str
    attempts: int
    solved_at: datetime | None = None
    best_time_seconds: int | None = None


class AssignmentDetail(AssignmentSummary):
    description: str | None = None
    puzzles: list[AssignmentPuzzleItem]


class GroupDetail(GroupSummary):
    upcoming_sessions: list[SessionSummary]
    recent_sessions: list[SessionSummary]
    assignments: list[AssignmentSummary]


class PuzzleDetail(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    assignment_title: str
    assignment_closed: bool
    display_order: int
    total_in_assignment: int
    previous_puzzle_id: uuid.UUID | None = None
    next_puzzle_id: uuid.UUID | None = None
    rating: int | None = None
    difficulty: str | None = None
    category: str | None = None
    themes: list[str]
    orientation: str
    moves_required: int
    position: PositionState
    status: str
    attempts: int
    # Revealed only once the student has solved the puzzle.
    solution_san: list[str] | None = None
    explanation: str | None = None


class AttemptRequest(BaseModel):
    assignment_id: uuid.UUID
    moves: list[str] = Field(min_length=1, max_length=50)
    time_taken_seconds: int | None = Field(default=None, ge=0, le=86400)
    hints_used: int = Field(default=0, ge=0, le=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("moves")
    @classmethod
    def moves_are_uci(cls, moves):
        return _check_uci_moves(moves)


def _check_uci_moves(moves: list[str]) -> list[str]:
    for move in moves:
        if not re.fullmatch(UCI_MOVE_PATTERN, move):
            raise ValueError(f"{move!r} is not a UCI move such as e2e4.")
    return moves


class HintRequest(BaseModel):
    assignment_id: uuid.UUID
    # The student's moves so far; empty for a hint at the first move.
    moves: list[str] = Field(default_factory=list, max_length=50)
    level: Literal[1, 2] = 1

    model_config = ConfigDict(extra="forbid")

    @field_validator("moves")
    @classmethod
    def moves_are_uci(cls, moves):
        return _check_uci_moves(moves)


class HintResponse(BaseModel):
    level: int
    from_square: str
    piece: str | None = None
    move: str | None = None
    san: str | None = None


class PlayedMoveOut(BaseModel):
    uci: str
    san: str
    fen: str
    by: str


class AwardedBadge(BaseModel):
    code: str
    name: str
    xp_reward: int


class AttemptResponse(BaseModel):
    status: str
    recorded: bool
    attempt_id: uuid.UUID | None = None
    played: list[PlayedMoveOut]
    position: PositionState
    already_solved: bool
    xp_awarded: int
    badges_awarded: list[AwardedBadge]
    solution_san: list[str] | None = None
    explanation: str | None = None
    assignment_status: str
    assignment_progress: AssignmentProgress
    assignment_completed_now: bool


# --- Gamification, progress and activity ------------------------------------


class GamificationSummary(BaseModel):
    total_xp: int
    current_streak: int
    longest_streak: int
    last_activity_date: date | None = None
    puzzles_solved: int
    games_played: int
    assignments_completed: int = 0
    level: str | None = None
    xp_level: "XPLevel"
    activity_calendar: list["CalendarDay"]
    active_days: int
    badges_earned: int
    badges_total: int
    recent_badges: list[BadgeItem]
    recent_xp: list[XPEventItem]
    next_milestone: Milestone | None = None


class XPLevel(BaseModel):
    level: int
    total_xp: int
    level_start_xp: int
    next_level_xp: int
    xp_into_level: int
    xp_to_next_level: int
    progress_percent: float


class CalendarDay(BaseModel):
    date: date
    puzzles_attempted: int
    puzzles_solved: int
    xp_earned: int


GamificationSummary.model_rebuild()


class ActivityItem(BaseModel):
    id: uuid.UUID
    puzzle_id: uuid.UUID
    assignment_id: uuid.UUID | None = None
    assignment_title: str | None = None
    is_solved: bool
    time_taken_seconds: int | None = None
    attempted_at: datetime
    rating: int | None = None
    difficulty: str | None = None
    themes: list[str]


class DailyItem(BaseModel):
    date: date
    puzzles_attempted: int
    puzzles_solved: int
    xp_earned: int


class BreakdownItem(BaseModel):
    label: str
    attempts: int
    solved_attempts: int
    puzzles_solved: int
    accuracy_percent: float


class ProgressSummary(BaseModel):
    puzzles_attempted: int
    puzzles_solved: int
    total_attempts: int
    solved_attempts: int
    accuracy_percent: float | None = None
    average_solve_time_seconds: float | None = None
    assignments_total: int
    assignments_completed: int
    assignment_completion_percent: float | None = None
    total_xp: int
    current_streak: int
    longest_streak: int
    daily: list[DailyItem]
    themes: list[BreakdownItem]
    difficulties: list[BreakdownItem]
    metric_definitions: dict[str, str]


# --- Dashboard ---------------------------------------------------------------


class DashboardProfile(BaseModel):
    full_name: str
    email: str
    avatar_url: str | None = None
    level: str
    chess_rating: int


class AssignmentCounts(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    overdue: int


class DashboardStats(BaseModel):
    puzzles_solved: int
    total_attempts: int
    accuracy_percent: float | None = None
    total_xp: int
    current_streak: int
    longest_streak: int
    badges_earned: int


class DashboardResponse(BaseModel):
    profile: DashboardProfile
    trainer: TrainerSummary | None = None
    groups: list[GroupMembershipItem]
    assignment_counts: AssignmentCounts
    active_assignments: list[AssignmentSummary]
    recently_completed: list[AssignmentSummary]
    upcoming_sessions: list[SessionSummary]
    recent_attempts: list[ActivityItem]
    stats: DashboardStats
    recent_badges: list[BadgeItem]
    next_milestone: Milestone | None = None
