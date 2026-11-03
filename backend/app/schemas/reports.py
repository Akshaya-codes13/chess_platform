import uuid
from datetime import date, datetime

from pydantic import BaseModel


class DailyCounters(BaseModel):
    sessions_held: int
    attendance_present: int
    attendance_late: int
    attendance_absent: int
    attendance_excused: int
    submissions: int
    active_students: int
    puzzle_attempts: int
    puzzles_solved: int


class PlatformCounters(DailyCounters):
    new_students: int
    new_trainers: int
    xp_awarded: int


class TrainerDailyPoint(DailyCounters):
    date: date
    # False when the job has not computed this day yet.
    computed: bool


class PlatformDailyPoint(PlatformCounters):
    date: date
    computed: bool


class TrainerTotals(DailyCounters):
    attendance_rate: float | None
    solve_rate: float | None


class PlatformTotals(PlatformCounters):
    attendance_rate: float | None
    solve_rate: float | None


class TrainerRow(TrainerTotals):
    trainer_id: uuid.UUID
    full_name: str


class StudentConsistency(BaseModel):
    student_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    active_days: int
    consistency_percent: float | None
    puzzles_solved: int
    xp_earned: int


class AdminDailyReport(BaseModel):
    start_date: date
    end_date: date
    days: int
    last_computed_at: datetime | None
    missing_days: list[date]
    totals: PlatformTotals
    series: list[PlatformDailyPoint]
    trainers: list[TrainerRow]
    students: list[StudentConsistency]


class TrainerDailyReport(BaseModel):
    start_date: date
    end_date: date
    days: int
    last_computed_at: datetime | None
    missing_days: list[date]
    totals: TrainerTotals
    series: list[TrainerDailyPoint]
    students: list[StudentConsistency]
