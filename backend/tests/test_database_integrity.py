import secrets
import uuid
from collections import defaultdict
from datetime import date

import chess
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models import (
    Assignment,
    AssignmentPuzzle,
    AssignmentRecipient,
    Badge,
    BoardPosition,
    ClassSession,
    DailyActivity,
    Game,
    GroupMember,
    Puzzle,
    PuzzleAttempt,
    PuzzleTheme,
    PuzzleThemeMapping,
    SessionAttendance,
    StudentBadge,
    StudentProfile,
    StudentProgress,
    User,
    XPEvent,
)
from app.services.xp_service import badge_counters
from scripts import seed


SEEDED_MODELS = [
    User,
    StudentProfile,
    GroupMember,
    Puzzle,
    PuzzleThemeMapping,
    Assignment,
    AssignmentPuzzle,
    AssignmentRecipient,
    ClassSession,
    SessionAttendance,
    Game,
    BoardPosition,
    Badge,
    StudentBadge,
    PuzzleAttempt,
    XPEvent,
    DailyActivity,
    StudentProgress,
]


def count_rows(db):
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in SEEDED_MODELS
    }


def assert_rejected(db, record):
    """Assert the database rejects the record, keeping the outer transaction."""
    savepoint = db.begin_nested()
    db.add(record)

    with pytest.raises(IntegrityError):
        db.flush()

    savepoint.rollback()


def demo_assignment(db):
    assignment = seed.get_demo_assignment(db)
    assert assignment is not None
    return assignment


def demo_session(db):
    session = db.scalar(
        select(ClassSession).where(
            ClassSession.start_time == seed.DEMO_SESSION["start_time"],
            ClassSession.title == seed.DEMO_SESSION["title"],
        )
    )
    assert session is not None
    return session


def demo_game(db):
    _, _, game = seed.get_demo_game(db)
    assert game is not None
    return game


def test_seed_is_idempotent(seeded_db):
    before = count_rows(seeded_db)

    seed.seed_all(seeded_db, hash_password(secrets.token_urlsafe(16)))

    assert count_rows(seeded_db) == before


@pytest.mark.parametrize(
    "data", seed.SAMPLE_PUZZLES, ids=lambda data: data["lichess_id"]
)
def test_sample_puzzle_is_valid(seeded_db, data):
    board = seed.validate_puzzle_solution(data["fen"], data["solution"])

    puzzle = seed.get_puzzle(seeded_db, data["lichess_id"])
    assert puzzle.fen == data["fen"]
    assert puzzle.solution == data["solution"]
    assert chess.Board(puzzle.fen).is_valid()

    if "checkmate" in data["themes"]:
        assert board.is_checkmate()


def test_puzzle_theme_mappings(seeded_db):
    for data in seed.SAMPLE_PUZZLES:
        puzzle = seed.get_puzzle(seeded_db, data["lichess_id"])
        theme_slugs = set(
            seeded_db.scalars(
                select(PuzzleTheme.slug)
                .join(PuzzleThemeMapping)
                .where(PuzzleThemeMapping.puzzle_id == puzzle.id)
            )
        )
        assert set(data["themes"]) <= theme_slugs

    covered = set(
        seeded_db.scalars(
            select(PuzzleTheme.slug).join(PuzzleThemeMapping).distinct()
        )
    )
    assert {"fork", "pin", "skewer", "discovered-attack", "checkmate"} <= covered


def test_unique_constraints(seeded_db):
    db = seeded_db
    assignment = demo_assignment(db)
    session = demo_session(db)
    student = seed.get_student_profile(db, seed.DEMO_STUDENT_EMAILS[0])
    puzzle = seed.get_puzzle(db, "demo-fork-001")
    fork = db.scalar(select(PuzzleTheme).where(PuzzleTheme.slug == "fork"))
    badge = db.scalar(select(Badge).where(Badge.code == "first-puzzle-solved"))
    activity_day = db.scalar(
        select(DailyActivity.activity_date).where(
            DailyActivity.student_id == student.id
        )
    )

    duplicates = [
        Puzzle(lichess_id=puzzle.lichess_id, fen=puzzle.fen, solution="b5d6"),
        PuzzleThemeMapping(puzzle_id=puzzle.id, theme_id=fork.id),
        AssignmentRecipient(assignment_id=assignment.id, student_id=student.id),
        AssignmentPuzzle(assignment_id=assignment.id, puzzle_id=puzzle.id),
        SessionAttendance(
            session_id=session.id, student_id=student.id, status="present"
        ),
        StudentBadge(student_id=student.id, badge_id=badge.id),
        DailyActivity(student_id=student.id, activity_date=activity_day),
        StudentProgress(student_id=student.id),
    ]

    for record in duplicates:
        assert_rejected(db, record)


def test_foreign_keys_are_enforced(seeded_db):
    db = seeded_db
    missing_id = uuid.uuid4()
    student = seed.get_student_profile(db, seed.DEMO_STUDENT_EMAILS[0])

    orphans = [
        BoardPosition(game_id=missing_id, fen=chess.STARTING_FEN),
        AssignmentRecipient(
            assignment_id=demo_assignment(db).id, student_id=missing_id
        ),
        SessionAttendance(
            session_id=missing_id, student_id=student.id, status="present"
        ),
        PuzzleAttempt(student_id=student.id, puzzle_id=missing_id),
        XPEvent(student_id=missing_id, points=10, reason="Orphan event"),
    ]

    for record in orphans:
        assert_rejected(db, record)


def test_assignment_recipients_and_puzzles(seeded_db):
    db = seeded_db
    assignment = demo_assignment(db)
    trainer = seed.get_demo_trainer_profile(db)
    group = seed.get_demo_group(db, trainer)

    assert assignment.trainer_id == trainer.id == group.trainer_id
    assert assignment.group_id == group.id
    assert assignment.assignment_type == "group"
    assert assignment.status == "published"
    assert assignment.published_at is not None

    recipients = set(
        db.scalars(
            select(AssignmentRecipient.student_id).where(
                AssignmentRecipient.assignment_id == assignment.id
            )
        )
    )
    members = set(
        db.scalars(
            select(GroupMember.student_id).where(
                GroupMember.group_id == group.id
            )
        )
    )
    demo_students = {
        seed.get_student_profile(db, email).id
        for email in seed.DEMO_STUDENT_EMAILS
    }
    assert demo_students <= recipients <= members

    puzzles = db.scalars(
        select(Puzzle.lichess_id)
        .join(AssignmentPuzzle)
        .where(AssignmentPuzzle.assignment_id == assignment.id)
        .order_by(AssignmentPuzzle.display_order)
    ).all()
    assert puzzles == seed.DEMO_ASSIGNMENT["puzzles"]


def test_session_attendance(seeded_db):
    db = seeded_db
    session = demo_session(db)
    trainer = seed.get_demo_trainer_profile(db)
    group = seed.get_demo_group(db, trainer)

    assert session.trainer_id == trainer.id
    assert session.group_id == group.id
    assert session.session_type == "group"
    assert session.status == "completed"
    assert session.end_time > session.start_time

    attendance = db.scalars(
        select(SessionAttendance).where(
            SessionAttendance.session_id == session.id
        )
    ).all()
    members = set(
        db.scalars(
            select(GroupMember.student_id).where(
                GroupMember.group_id == group.id
            )
        )
    )

    assert len(attendance) == len(seed.DEMO_SESSION["attendance"])

    for record in attendance:
        assert record.student_id in members
        assert record.status in {"present", "absent", "late", "excused"}


def test_game_and_board_positions(seeded_db):
    db = seeded_db
    game = demo_game(db)

    board, fens = seed.replay_game(game.initial_fen, game.moves)

    assert game.white_id != game.black_id
    assert game.status == "completed"
    assert game.current_fen == board.fen()
    assert board.outcome().winner == seed.GAME_RESULTS[game.result]
    assert game.started_at < game.ended_at

    positions = db.scalars(
        select(BoardPosition)
        .where(BoardPosition.game_id == game.id)
        .order_by(BoardPosition.move_number)
    ).all()

    assert [p.move_number for p in positions] == sorted(
        seed.DEMO_GAME["snapshots"]
    )

    for position in positions:
        assert position.fen == fens[position.move_number]


@pytest.mark.parametrize("email", seed.DEMO_STUDENT_EMAILS)
def test_student_progress_consistency(seeded_db, email):
    db = seeded_db
    student = seed.get_student_profile(db, email)

    progress = db.scalar(
        select(StudentProgress).where(StudentProgress.student_id == student.id)
    )
    assert progress is not None

    xp_events = db.scalars(
        select(XPEvent).where(XPEvent.student_id == student.id)
    ).all()
    attempts = db.scalars(
        select(PuzzleAttempt).where(PuzzleAttempt.student_id == student.id)
    ).all()
    games = seed.get_completed_games(db, student.user_id)

    assert progress.total_xp == sum(event.points for event in xp_events)
    assert progress.puzzles_solved == sum(a.is_solved for a in attempts)
    assert progress.games_played == len(games)

    # Every solved attempt earns exactly one XP event.
    solved_ids = {a.id for a in attempts if a.is_solved}
    puzzle_event_ids = [
        e.source_id for e in xp_events if e.source_type == "puzzle_attempt"
    ]
    assert sorted(puzzle_event_ids) == sorted(solved_ids)

    # Daily activity rows add up to the underlying records.
    expected = defaultdict(lambda: defaultdict(int))

    for attempt in attempts:
        day = expected[seed.activity_date(attempt.attempted_at)]
        day["puzzles_attempted"] += 1
        day["puzzles_solved"] += int(attempt.is_solved)

    for game in games:
        expected[seed.activity_date(game.ended_at)]["games_played"] += 1

    for event in xp_events:
        expected[seed.activity_date(event.created_at)]["xp_earned"] += event.points

    activity = db.scalars(
        select(DailyActivity).where(DailyActivity.student_id == student.id)
    ).all()

    assert {row.activity_date for row in activity} == set(expected)

    for row in activity:
        totals = expected[row.activity_date]
        assert row.puzzles_attempted == totals["puzzles_attempted"]
        assert row.puzzles_solved == totals["puzzles_solved"]
        assert row.games_played == totals["games_played"]
        assert row.xp_earned == totals["xp_earned"]

    _, longest = seed.calculate_streaks(expected)
    assert progress.longest_streak == longest
    assert 0 <= progress.current_streak <= progress.longest_streak

    # Badges are awarded exactly when their requirement is met.
    earned = set(
        db.scalars(
            select(Badge.code)
            .join(StudentBadge)
            .where(StudentBadge.student_id == student.id)
        )
    )

    counters = badge_counters(db, progress)

    for code, (counter, threshold) in seed.BADGE_REQUIREMENTS.items():
        assert (code in earned) == (counters[counter] >= threshold)


def test_calculate_streaks():
    days = [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
            date(2026, 10, 5), date(2026, 10, 6)]

    assert seed.calculate_streaks(days) == (2, 3)
    assert seed.calculate_streaks([]) == (0, 0)
