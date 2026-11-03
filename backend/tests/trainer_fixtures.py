"""Fixtures and factories for the Trainer module tests.

``tdb`` runs each test inside one outer transaction that is rolled back at
the end. The API shares that session (``get_db`` is overridden), and
service-level commits only release savepoints, so tests can call endpoints
freely and nothing persists.

Import the fixtures into a test module with
``from tests.trainer_fixtures import *  # noqa: F401,F403``.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.core.security import create_access_token
from app.main import app
from app.models import (
    ClassSession,
    Group,
    GroupMember,
    Puzzle,
    PuzzleAttempt,
    StudentProfile,
    TrainerProfile,
    User,
)

__all__ = ["tdb", "api", "factory", "headers", "MATE_IN_ONE", "FORK", "now"]

MATE_IN_ONE = ("7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "g6g7")
FORK = ("2q1k3/8/8/1N6/8/8/8/K7 w - - 0 1", "b5d6")


def now() -> datetime:
    return datetime.now(timezone.utc)


def headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture()
def tdb():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture()
def api(tdb):
    return TestClient(app)


class Factory:
    def __init__(self, db: Session):
        self.db = db

    def user(self, role: str, name: str = "Test User") -> User:
        user = User(
            email=f"m5-{uuid.uuid4().hex}@example.com",
            password_hash="not-used",
            full_name=name,
            role=role,
            is_active=True,
            is_verified=True,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def trainer(self, name: str = "Trainer") -> tuple[User, TrainerProfile]:
        user = self.user("trainer", name)
        profile = TrainerProfile(user_id=user.id, experience_years=2)
        self.db.add(profile)
        self.db.flush()
        return user, profile

    def student(self, trainer: TrainerProfile, name: str = "Student") -> StudentProfile:
        user = self.user("student", name)
        profile = StudentProfile(user_id=user.id, trainer_id=trainer.id, chess_rating=900)
        self.db.add(profile)
        self.db.flush()
        return profile

    def group(self, trainer: TrainerProfile, students=(), name: str | None = None, is_active=True) -> Group:
        group = Group(trainer_id=trainer.id, name=name or f"Group {uuid.uuid4().hex[:6]}", is_active=is_active)
        self.db.add(group)
        self.db.flush()
        for student in students:
            self.db.add(GroupMember(group_id=group.id, student_id=student.id))
        self.db.flush()
        return group

    def puzzle(self, fen_solution=MATE_IN_ONE, status="published", owner: TrainerProfile | None = None, rating=1000) -> Puzzle:
        fen, solution = fen_solution
        puzzle = Puzzle(
            fen=fen, solution=solution, status=status, rating=rating,
            difficulty="beginner", source="test",
            created_by_trainer_id=owner.id if owner else None,
        )
        self.db.add(puzzle)
        self.db.flush()
        return puzzle

    def attempt(self, student, puzzle, solved: bool, assignment_id=None, when=None) -> PuzzleAttempt:
        attempt = PuzzleAttempt(
            student_id=student.id, puzzle_id=puzzle.id, assignment_id=assignment_id,
            is_solved=solved, time_taken_seconds=30, attempted_at=when or now(),
        )
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def session(self, trainer, group, start: datetime, hours: float = 1, status="scheduled") -> ClassSession:
        session = ClassSession(
            trainer_id=trainer.id, group_id=group.id, title="Tactics class",
            session_type="group", status=status,
            start_time=start, end_time=start + timedelta(hours=hours),
        )
        self.db.add(session)
        self.db.flush()
        return session


@pytest.fixture()
def factory(tdb):
    return Factory(tdb)
