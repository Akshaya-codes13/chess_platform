import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.puzzle import reject_duplicate_ids

MAX_ASSIGNMENT_PUZZLES = 50


def check_date_order(model):
    if model.start_date and model.due_date and model.due_date < model.start_date:
        raise ValueError("Due date cannot be earlier than the start date.")
    return model


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    group_id: uuid.UUID
    puzzle_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_ASSIGNMENT_PUZZLES)
    # None assigns the whole group; a list targets those group members only.
    student_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    start_date: AwareDatetime | None = None
    due_date: AwareDatetime | None = None
    publish: bool = False

    check_puzzle_ids = field_validator("puzzle_ids")(reject_duplicate_ids)
    check_student_ids = field_validator("student_ids")(reject_duplicate_ids)
    check_dates = model_validator(mode="after")(check_date_order)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Title must be at least 3 characters.")
        return value


class AssignmentUpdate(BaseModel):
    """Partial update of a draft. Sending ``student_ids: null`` switches the
    assignment back to the whole group; omitting it keeps the recipients."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    group_id: uuid.UUID | None = None
    puzzle_ids: list[uuid.UUID] | None = Field(default=None, max_length=MAX_ASSIGNMENT_PUZZLES)
    student_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    start_date: AwareDatetime | None = None
    due_date: AwareDatetime | None = None

    check_puzzle_ids = field_validator("puzzle_ids")(reject_duplicate_ids)
    check_student_ids = field_validator("student_ids")(reject_duplicate_ids)
    check_dates = model_validator(mode="after")(check_date_order)


class GroupRef(BaseModel):
    id: uuid.UUID
    name: str


class AssignmentSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    assignment_type: str
    group: GroupRef | None
    start_date: datetime | None
    due_date: datetime | None
    published_at: datetime | None
    created_at: datetime
    puzzle_count: int
    recipient_count: int
    completed_count: int


class AssignmentPuzzleItem(BaseModel):
    puzzle_id: uuid.UUID
    display_order: int
    points: int
    fen: str
    rating: int | None
    difficulty: str | None
    status: str


class AssignmentRecipientItem(BaseModel):
    student_id: uuid.UUID
    full_name: str
    email: str


class AssignmentDetail(AssignmentSummary):
    description: str | None
    puzzles: list[AssignmentPuzzleItem]
    recipients: list[AssignmentRecipientItem]


class RecipientProgress(BaseModel):
    student_id: uuid.UUID
    full_name: str
    email: str
    puzzles_total: int
    puzzles_attempted: int
    puzzles_solved: int
    attempts: int
    completion_percent: float
    status: Literal["not_started", "in_progress", "completed"]
    last_activity_at: datetime | None
    submission_status: str | None
    submission_score: int | None
    submission_id: uuid.UUID | None = None
    trainer_feedback: str | None = None


class AssignmentProgress(BaseModel):
    assignment_id: uuid.UUID
    title: str
    status: str
    due_date: datetime | None
    is_overdue: bool
    puzzles_total: int
    recipients_total: int
    completed_count: int
    in_progress_count: int
    not_started_count: int
    completion_rate: float | None
    average_completion_percent: float | None
    recipients: list[RecipientProgress]


class ReviewAttempt(BaseModel):
    id: uuid.UUID
    is_solved: bool
    moves: list[str]
    hints_used: int
    time_taken_seconds: int | None
    attempted_at: datetime


class ReviewPuzzle(BaseModel):
    puzzle_id: uuid.UUID
    display_order: int
    rating: int | None
    fen: str
    points: int
    solved: bool
    attempts: list[ReviewAttempt]


class SubmissionInfo(BaseModel):
    id: uuid.UUID
    attempt_number: int
    status: str
    score: int | None
    submitted_at: datetime
    trainer_feedback: str | None


class StudentSubmission(BaseModel):
    assignment_id: uuid.UUID
    assignment_title: str
    student_id: uuid.UUID
    full_name: str
    email: str
    total_points: int
    earned_points: int
    puzzles: list[ReviewPuzzle]
    submission: SubmissionInfo | None


class SubmissionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 'graded' accepts the work; 'returned' sends it back with feedback.
    status: Literal["graded", "returned"]
    score: int | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=5000)
