"""Fixtures for Student module tests.

``tx_db`` binds the API's ``get_db`` to one connection-level transaction;
service commits become savepoints and everything is rolled back afterwards,
so these tests never leave rows behind and never depend on existing data.
``world`` builds an isolated academy: one trainer, students A and B, a
shared group, puzzles, assignments with different visibility, and sessions.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import (
    Assignment,
    AssignmentPuzzle,
    AssignmentRecipient,
    Badge,
    ClassSession,
    Group,
    GroupMember,
    Puzzle,
    PuzzleTheme,
    PuzzleThemeMapping,
    SessionAttendance,
    StudentProfile,
    TrainerProfile,
    User,
)
from scripts import seed
from tests.conftest import auth_headers

MATE_IN_ONE = ("7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "g6g7")
PIN = ("6k1/p5pp/8/3q4/8/1P6/P4PPP/5BK1 w - - 0 1", "f1c4 d5c4 b3c4")
SKEWER = ("8/p5pp/3k3q/8/8/8/5PPP/R5K1 w - - 0 1", "a1a6 d6e5 a6h6")


@pytest.fixture()
def tx_db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
    )
    app.dependency_overrides[get_db] = lambda: session

    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def api():
    return TestClient(app)


def _user(db, role, name):
    user = User(
        email=f"m6-{uuid.uuid4().hex}@example.com",
        password_hash="not-a-real-hash",
        full_name=name,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _puzzle(db, fen, solution, rating, difficulty, theme=None):
    puzzle = Puzzle(
        fen=fen,
        solution=solution,
        rating=rating,
        difficulty=difficulty,
        explanation="Test explanation.",
    )
    db.add(puzzle)
    db.flush()

    if theme is not None:
        db.add(PuzzleThemeMapping(puzzle_id=puzzle.id, theme_id=theme.id))

    return puzzle


def _assignment(db, trainer, title, puzzles, recipients, group=None, **fields):
    assignment = Assignment(
        trainer_id=trainer.id,
        group_id=group.id if group else None,
        title=title,
        description=f"{title} instructions.",
        assignment_type="group" if group else "individual",
        status=fields.pop("status", "published"),
        published_at=datetime.now(timezone.utc) - timedelta(days=1),
        **fields,
    )
    db.add(assignment)
    db.flush()

    for order, puzzle in enumerate(puzzles, start=1):
        db.add(
            AssignmentPuzzle(
                assignment_id=assignment.id,
                puzzle_id=puzzle.id,
                points=order,
                display_order=order,
            )
        )

    for student in recipients:
        db.add(AssignmentRecipient(assignment_id=assignment.id, student_id=student.id))

    db.flush()
    return assignment


def _session(db, trainer, title, start, status, group=None, session_type="group"):
    session = ClassSession(
        trainer_id=trainer.id,
        group_id=group.id if group else None,
        title=title,
        session_type=session_type,
        status=status,
        start_time=start,
        end_time=start + timedelta(hours=1),
        meeting_url="https://meet.example.com/class",
    )
    db.add(session)
    db.flush()
    return session


@pytest.fixture()
def world(tx_db):
    db = tx_db
    now = datetime.now(timezone.utc)

    for data in seed.DEMO_BADGES:
        if db.scalar(select(Badge).where(Badge.code == data["code"])) is None:
            db.add(Badge(**data))

    theme = db.scalar(select(PuzzleTheme).where(PuzzleTheme.slug == "m6-test-theme"))

    if theme is None:
        theme = PuzzleTheme(name="M6 Test Theme", slug="m6-test-theme")
        db.add(theme)
        db.flush()

    trainer_user = _user(db, "trainer", "Test Trainer")
    trainer = TrainerProfile(
        user_id=trainer_user.id, specialization="Tactics", experience_years=5
    )
    db.add(trainer)
    db.flush()

    users = {}
    students = {}

    for key in ("a", "b"):
        users[key] = _user(db, "student", f"Student {key.upper()}")
        students[key] = StudentProfile(
            user_id=users[key].id, trainer_id=trainer.id, chess_rating=900
        )
        db.add(students[key])

    db.flush()

    group = Group(trainer_id=trainer.id, name="M6 Test Group", is_active=True)
    db.add(group)
    db.flush()

    for student in students.values():
        db.add(GroupMember(group_id=group.id, student_id=student.id))

    mate = _puzzle(db, *MATE_IN_ONE, 800, "beginner", theme)
    pin = _puzzle(db, *PIN, 950, "beginner", theme)
    skewer = _puzzle(db, *SKEWER, 1000, "intermediate")
    broken = _puzzle(db, "not a fen", "e2e4", 500, "beginner")
    unassigned = _puzzle(db, *MATE_IN_ONE, 800, "beginner")

    a, b = students["a"], students["b"]
    shared = _assignment(
        db, trainer, "Shared tactics", [mate, pin, skewer], [a, b], group,
        due_date=now + timedelta(days=7),
    )
    b_only = _assignment(
        db, trainer, "Only for B", [mate], [b], due_date=now + timedelta(days=7)
    )
    overdue = _assignment(
        db, trainer, "Overdue set", [skewer], [a], due_date=now - timedelta(days=1)
    )
    draft = _assignment(db, trainer, "Draft set", [mate], [a], status="draft")
    future = _assignment(
        db, trainer, "Not started", [mate], [a], start_date=now + timedelta(days=2)
    )
    invalid = _assignment(db, trainer, "Broken puzzle set", [broken], [a])
    closed = _assignment(db, trainer, "Closed set", [pin], [a], status="completed")

    upcoming = _session(db, trainer, "Upcoming group class", now + timedelta(days=1), "scheduled", group)
    past = _session(db, trainer, "Past group class", now - timedelta(days=2), "completed", group)
    b_private = _session(
        db, trainer, "B private lesson", now + timedelta(days=3), "scheduled",
        session_type="individual",
    )
    db.add(SessionAttendance(session_id=past.id, student_id=a.id, status="present"))
    db.add(SessionAttendance(session_id=past.id, student_id=b.id, status="absent", remarks="Private note for B"))
    db.add(SessionAttendance(session_id=b_private.id, student_id=b.id, status="scheduled"))
    db.flush()

    return SimpleNamespace(
        db=db,
        trainer_user=trainer_user,
        trainer=trainer,
        users=users,
        students=students,
        headers={key: auth_headers(user) for key, user in users.items()},
        trainer_headers=auth_headers(trainer_user),
        group=group,
        puzzles=SimpleNamespace(
            mate=mate, pin=pin, skewer=skewer, broken=broken, unassigned=unassigned
        ),
        assignments=SimpleNamespace(
            shared=shared, b_only=b_only, overdue=overdue, draft=draft,
            future=future, invalid=invalid, closed=closed,
        ),
        sessions=SimpleNamespace(upcoming=upcoming, past=past, b_private=b_private),
    )


def attempt(api, world, student, puzzle, assignment, moves, **extra):
    return api.post(
        f"/student/puzzles/{puzzle.id}/attempts",
        json={"assignment_id": str(assignment.id), "moves": moves, **extra},
        headers=world.headers[student],
    )
