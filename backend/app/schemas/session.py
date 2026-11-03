import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.assignment import GroupRef

AttendanceStatus = Literal["present", "absent", "late", "excused"]

MAX_SESSION_HOURS = 8


def check_meeting_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.startswith(("https://", "http://")):
        raise ValueError("Meeting URL must start with http:// or https://.")
    return value


def check_time_range(model):
    if model.start_time and model.end_time:
        if model.end_time <= model.start_time:
            raise ValueError("End time must be after start time.")
        if (model.end_time - model.start_time).total_seconds() > MAX_SESSION_HOURS * 3600:
            raise ValueError(f"A session cannot be longer than {MAX_SESSION_HOURS} hours.")
    return model


class SessionCreate(BaseModel):
    """Times must include a UTC offset; they are stored in UTC."""

    model_config = ConfigDict(extra="forbid")

    group_id: uuid.UUID
    # Optional subset of the group's students (student profile IDs). When
    # given, only these students are invited and see the session.
    student_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=200)
    title: str = Field(min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    learning_objective: str | None = Field(default=None, max_length=2000)
    start_time: AwareDatetime
    end_time: AwareDatetime
    meeting_url: str | None = Field(default=None, max_length=500)

    check_url = field_validator("meeting_url")(check_meeting_url)
    check_times = model_validator(mode="after")(check_time_range)

    @field_validator("student_ids")
    @classmethod
    def unique_students(cls, ids):
        if ids is not None and len(set(ids)) != len(ids):
            raise ValueError("Each student can appear only once.")
        return ids


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    learning_objective: str | None = Field(default=None, max_length=2000)
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    meeting_url: str | None = Field(default=None, max_length=500)

    check_url = field_validator("meeting_url")(check_meeting_url)
    check_times = model_validator(mode="after")(check_time_range)


class SessionSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    # 'group': the whole group; 'individual': only the selected students.
    session_type: str = "group"
    is_active: bool = False
    group: GroupRef | None
    start_time: datetime
    end_time: datetime
    learning_objective: str | None
    meeting_url: str | None
    roster_size: int
    attendance_recorded: int


class RosterEntry(BaseModel):
    student_id: uuid.UUID
    full_name: str
    email: str
    attendance_status: str | None
    remarks: str | None


class AttendanceSummary(BaseModel):
    present: int
    absent: int
    late: int
    excused: int
    unrecorded: int


class SessionDetail(SessionSummary):
    description: str | None
    can_edit: bool
    can_record_attendance: bool
    roster: list[RosterEntry]
    attendance_summary: AttendanceSummary


class AttendanceEntry(BaseModel):
    student_id: uuid.UUID
    status: AttendanceStatus
    remarks: str | None = Field(default=None, max_length=500)


class AttendanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[AttendanceEntry] = Field(min_length=1, max_length=500)

    @field_validator("records")
    @classmethod
    def unique_students(cls, records: list[AttendanceEntry]) -> list[AttendanceEntry]:
        ids = [record.student_id for record in records]
        if len(set(ids)) != len(ids):
            raise ValueError("Each student can appear only once.")
        return records
