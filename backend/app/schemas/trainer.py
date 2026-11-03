import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.assignment import AssignmentSummary, GroupRef
from app.schemas.session import SessionSummary


class TrainerProfileResponse(BaseModel):
    user_id: uuid.UUID
    trainer_profile_id: uuid.UUID
    email: str
    full_name: str
    role: str
    phone: str | None
    avatar_url: str | None
    language: str
    is_active: bool
    is_verified: bool
    bio: str | None
    specialization: str | None
    experience_years: int
    created_at: datetime
    last_login_at: datetime | None


class TrainerProfileUpdate(BaseModel):
    """Fields a trainer may change. Role, status and email are Admin-managed;
    sending them is rejected rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\+?[0-9 ()-]{6,20}$")
    avatar_url: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    bio: str | None = Field(default=None, max_length=2000)
    specialization: str | None = Field(default=None, max_length=150)
    experience_years: int | None = Field(default=None, ge=0, le=80)

    @field_validator("avatar_url")
    @classmethod
    def check_avatar_url(cls, value: str | None) -> str | None:
        if value and not value.startswith("https://"):
            raise ValueError("Avatar URL must start with https://.")
        return value or None


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    student_count: int
    created_at: datetime


class GroupDetail(GroupSummary):
    upcoming_session_count: int
    completed_session_count: int
    active_assignment_count: int
    next_session_at: datetime | None


class GroupStudent(BaseModel):
    student_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    chess_rating: int
    level: str
    is_active: bool
    joined_at: datetime


class StudentMetrics(BaseModel):
    puzzles_attempted: int
    puzzles_solved: int
    total_attempts: int
    solved_attempts: int
    accuracy_percent: float | None
    last_attempt_at: datetime | None
    assignments_received: int
    assignments_completed: int
    assignment_completion_rate: float | None
    sessions_recorded: int
    sessions_attended: int
    attendance_rate: float | None
    total_xp: int
    current_streak: int
    longest_streak: int
    badges_count: int


class BadgeItem(BaseModel):
    code: str
    name: str
    description: str | None
    earned_at: datetime


class ProgressPoint(BaseModel):
    week_start: date
    attempts: int
    solved: int
    accuracy_percent: float | None


class ActivityItem(BaseModel):
    kind: str
    occurred_at: datetime
    description: str
    student_id: uuid.UUID
    student_name: str | None = None
    is_solved: bool | None = None


class StudentAssignmentItem(BaseModel):
    assignment_id: uuid.UUID
    title: str
    status: str
    due_date: datetime | None
    puzzles_total: int
    puzzles_solved: int
    completed: bool


class StudentPerformance(BaseModel):
    student: GroupStudent
    groups: list[GroupRef]
    metrics: StudentMetrics
    badges: list[BadgeItem]
    progress: list[ProgressPoint]
    recent_activity: list[ActivityItem]
    assignments: list[StudentAssignmentItem]


class GroupMetrics(BaseModel):
    student_count: int
    active_students: int
    total_attempts: int
    solved_attempts: int
    accuracy_percent: float | None
    assignments_received: int
    assignments_completed: int
    assignment_completion_rate: float | None
    sessions_recorded: int
    sessions_attended: int
    attendance_rate: float | None
    total_xp: int


class GroupStudentPerformance(GroupStudent):
    metrics: StudentMetrics


class GroupPerformance(BaseModel):
    group: GroupRef
    metrics: GroupMetrics
    students: list[GroupStudentPerformance]


class DashboardSummary(BaseModel):
    group_count: int
    student_count: int
    puzzles_created: int
    active_assignments: int
    upcoming_sessions: int
    completed_sessions: int


class DashboardPerformance(BaseModel):
    window_days: int
    attempts: int
    solved: int
    accuracy_percent: float | None
    active_students: int
    assignment_completion_rate: float | None
    attendance_rate: float | None


class DashboardResponse(BaseModel):
    profile: TrainerProfileResponse
    summary: DashboardSummary
    performance: DashboardPerformance
    upcoming_sessions: list[SessionSummary]
    recent_completed_sessions: list[SessionSummary]
    recent_assignments: list[AssignmentSummary]
    groups: list[GroupSummary]
    recent_activity: list[ActivityItem]
