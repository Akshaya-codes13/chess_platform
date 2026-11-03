import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.auth import validate_password_strength

Role = Literal["admin", "trainer", "student"]
CreatableRole = Literal["trainer", "student"]
StudentLevel = Literal["beginner", "intermediate", "advanced", "expert"]


class StrictModel(BaseModel):
    # Unknown fields are rejected, so a client cannot slip ``role`` or
    # ``password_hash`` into a profile update.
    model_config = ConfigDict(extra="forbid")


def _unique_ids(values: list[uuid.UUID]) -> list[uuid.UUID]:
    if len(set(values)) != len(values):
        raise ValueError("IDs must not contain duplicates.")
    return values


def _birth_date_in_past(value: date | None) -> date | None:
    if value is not None and value >= date.today():
        raise ValueError("Date of birth must be in the past.")
    return value


# ----- Shared references ---------------------------------------------------


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class GroupRef(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool


# ----- Users ---------------------------------------------------------------


class AdminUserSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    phone: str | None = None
    avatar_url: str | None = None
    language: str
    is_active: bool
    is_verified: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainerProfileOut(BaseModel):
    id: uuid.UUID
    bio: str | None = None
    specialization: str | None = None
    experience_years: int

    model_config = ConfigDict(from_attributes=True)


class StudentProfileOut(BaseModel):
    id: uuid.UUID
    date_of_birth: date | None = None
    chess_rating: int
    level: str
    notes: str | None = None
    trainer: UserRef | None = None


class TrainerStats(BaseModel):
    group_count: int
    active_group_count: int
    primary_student_count: int
    group_student_count: int
    upcoming_session_count: int
    assignment_count: int


class StudentProgressOut(BaseModel):
    total_xp: int
    current_streak: int
    longest_streak: int
    puzzles_solved: int
    games_played: int

    model_config = ConfigDict(from_attributes=True)


class StudentAssignmentOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    due_date: datetime | None = None
    trainer: UserRef
    latest_submission_status: str | None = None
    latest_score: int | None = None
    attempts: int


class AdminUserDetail(AdminUserSummary):
    trainer_profile: TrainerProfileOut | None = None
    student_profile: StudentProfileOut | None = None
    # Groups the student belongs to, or groups the trainer runs.
    groups: list[GroupRef] = []
    trainer_stats: TrainerStats | None = None
    student_progress: StudentProgressOut | None = None
    assignments: list[StudentAssignmentOut] = []


class TrainerListItem(AdminUserSummary):
    # Profile fields are null for a trainer account that has no profile yet.
    specialization: str | None = None
    experience_years: int | None = None
    group_count: int
    primary_student_count: int


class StudentListItem(AdminUserSummary):
    # Null for self-registered students who have no profile yet.
    level: str | None = None
    chess_rating: int | None = None
    trainer: UserRef | None = None
    group_count: int
    total_xp: int


class TrainerProfileIn(StrictModel):
    bio: str | None = Field(default=None, max_length=5000)
    specialization: str | None = Field(default=None, max_length=150)
    experience_years: int = Field(default=0, ge=0, le=80)


class TrainerProfileUpdate(StrictModel):
    bio: str | None = Field(default=None, max_length=5000)
    specialization: str | None = Field(default=None, max_length=150)
    experience_years: int | None = Field(default=None, ge=0, le=80)


class StudentProfileIn(StrictModel):
    trainer_user_id: uuid.UUID
    date_of_birth: date | None = None
    chess_rating: int = Field(default=0, ge=0, le=4000)
    level: StudentLevel = "beginner"
    notes: str | None = Field(default=None, max_length=5000)

    check_birth_date = field_validator("date_of_birth")(_birth_date_in_past)


class StudentProfileUpdate(StrictModel):
    trainer_user_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    chess_rating: int | None = Field(default=None, ge=0, le=4000)
    level: StudentLevel | None = None
    notes: str | None = Field(default=None, max_length=5000)

    check_birth_date = field_validator("date_of_birth")(_birth_date_in_past)


class AccountCreateBase(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)

    check_password = field_validator("password")(validate_password_strength)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return value


class TrainerCreate(AccountCreateBase):
    profile: TrainerProfileIn = TrainerProfileIn()


class StudentCreate(AccountCreateBase):
    profile: StudentProfileIn


class AdminUserCreate(AccountCreateBase):
    # Admin accounts are never created directly; an existing user is
    # promoted through the role endpoint instead.
    role: CreatableRole
    trainer_profile: TrainerProfileIn | None = None
    student_profile: StudentProfileIn | None = None

    @model_validator(mode="after")
    def profile_matches_role(self):
        if self.role == "student":
            if self.student_profile is None:
                raise ValueError("student_profile is required for students.")
            if self.trainer_profile is not None:
                raise ValueError("trainer_profile is not allowed for students.")
        if self.role == "trainer" and self.student_profile is not None:
            raise ValueError("student_profile is not allowed for trainers.")
        return self


class AdminUserUpdate(StrictModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    trainer_profile: TrainerProfileUpdate | None = None
    student_profile: StudentProfileUpdate | None = None

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Full name cannot be null.")
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return value

    @field_validator("email", "language")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null.")
        return value


class RoleChangeRequest(StrictModel):
    role: Role
    # Needed when a user becomes a student and has no student profile yet.
    trainer_user_id: uuid.UUID | None = None


class StatusChangeRequest(StrictModel):
    is_active: bool


# ----- Groups --------------------------------------------------------------


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    trainer: UserRef
    member_count: int
    created_at: datetime
    updated_at: datetime


class GroupMemberOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool
    level: str
    chess_rating: int
    joined_at: datetime


class GroupDetail(GroupSummary):
    members: list[GroupMemberOut]
    upcoming_session_count: int
    assignment_count: int


class GroupCreate(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    trainer_user_id: uuid.UUID
    is_active: bool = True
    student_user_ids: list[uuid.UUID] = Field(default=[], max_length=200)

    unique_students = field_validator("student_user_ids")(_unique_ids)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Group name must be at least 2 characters.")
        return value


class GroupUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Group name cannot be null.")
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Group name must be at least 2 characters.")
        return value

    @field_validator("is_active")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null.")
        return value


class GroupTrainerAssign(StrictModel):
    trainer_user_id: uuid.UUID


class GroupStudentsAdd(StrictModel):
    student_user_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)

    unique_students = field_validator("student_user_ids")(_unique_ids)


# ----- Puzzles -------------------------------------------------------------


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class ThemeOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class PuzzleSummary(BaseModel):
    id: uuid.UUID
    lichess_id: str | None = None
    fen: str
    rating: int | None = None
    type: str
    status: str
    difficulty: str | None = None
    source: str
    author: UserRef | None = None
    category: CategoryOut | None = None
    themes: list[ThemeOut]
    issues: list[str]
    created_at: datetime


class PuzzleUsage(BaseModel):
    assignment_count: int
    attempt_count: int
    solved_count: int


class PuzzleDetail(PuzzleSummary):
    solution: str
    explanation: str | None = None
    rating_deviation: int | None = None
    popularity: int | None = None
    usage: PuzzleUsage


class PuzzleFilterOptions(BaseModel):
    categories: list[CategoryOut]
    themes: list[ThemeOut]
    types: list[str]
    sources: list[str]
    statuses: list[str]


# ----- Oversight -----------------------------------------------------------


class AssignmentOverviewItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    assignment_type: str
    due_date: datetime | None = None
    published_at: datetime | None = None
    trainer: UserRef
    group: GroupRef | None = None
    recipient_count: int
    submission_count: int
    puzzle_count: int
    created_at: datetime


class SessionOverviewItem(BaseModel):
    id: uuid.UUID
    title: str
    session_type: str
    status: str
    start_time: datetime
    end_time: datetime
    trainer: UserRef
    group: GroupRef | None = None
    attendance: dict[str, int]


class ActivityItem(BaseModel):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    actor: UserRef | None = None
    details: dict
    occurred_at: datetime


class UserCounts(BaseModel):
    total: int
    active: int
    inactive: int
    admins: int
    trainers: int
    students: int


class GroupCounts(BaseModel):
    total: int
    active: int


class SessionCounts(BaseModel):
    upcoming: int
    completed: int
    total: int


class AssignmentCounts(BaseModel):
    total: int
    by_status: dict[str, int]


class DashboardResponse(BaseModel):
    users: UserCounts
    groups: GroupCounts
    puzzles: int
    assignments: AssignmentCounts
    sessions: SessionCounts
    recent_activity: list[ActivityItem]
    recent_users: list[AdminUserSummary]
    top_groups: list[GroupSummary]


class TopStudent(BaseModel):
    id: uuid.UUID
    full_name: str
    total_xp: int
    current_streak: int
    puzzles_solved: int


class GamificationReport(BaseModel):
    students_with_progress: int
    total_xp: int
    average_xp: float
    badges_defined: int
    badges_awarded: int
    top_students: list[TopStudent]


class PuzzleAttemptReport(BaseModel):
    total: int
    solved: int
    solve_rate: float


class GameReport(BaseModel):
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_result: dict[str, int]


class ReportsOverview(BaseModel):
    assignments_by_status: dict[str, int]
    submissions_by_status: dict[str, int]
    sessions_by_status: dict[str, int]
    attendance_by_status: dict[str, int]
    attendance_rate: float | None = None
    games: GameReport
    puzzle_attempts: PuzzleAttemptReport
    gamification: GamificationReport
