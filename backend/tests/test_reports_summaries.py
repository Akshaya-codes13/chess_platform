"""M11 precomputed daily summaries and the reports that read them, plus the
Lichess puzzle importer (M6)."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import DailyPlatformSummary, DailyTrainerSummary, Puzzle, PuzzleAttempt
from app.services import summary_service
from app.services.streak_service import today_utc
from scripts import import_lichess_puzzles as lichess
from tests.student_world import *  # noqa: F401,F403
from tests.student_world import _user, attempt, auth_headers


def test_compute_day_matches_source_records(api, world):
    shared = world.assignments.shared
    attempt(api, world, "a", world.puzzles.mate, shared, ["g6g7"])
    attempt(api, world, "b", world.puzzles.pin, shared, ["f1e2"])
    today = today_utc()

    row = summary_service.compute_day(world.db, today)

    start, end = summary_service._bounds(today)
    expected_attempts = world.db.scalar(
        select(func.count()).where(PuzzleAttempt.attempted_at >= start, PuzzleAttempt.attempted_at < end)
    )
    assert row["puzzle_attempts"] == expected_attempts
    assert row["puzzles_solved"] >= 1

    trainer_row = world.db.scalar(
        select(DailyTrainerSummary).where(
            DailyTrainerSummary.trainer_id == world.trainer.id, DailyTrainerSummary.summary_date == today
        )
    )
    assert trainer_row.puzzle_attempts == 2
    assert trainer_row.puzzles_solved == 1
    assert trainer_row.active_students == 2

    # Re-running updates the same row instead of adding another.
    attempt(api, world, "a", world.puzzles.pin, shared, ["f1e2"])
    summary_service.compute_day(world.db, today)
    rows = world.db.scalars(
        select(DailyTrainerSummary).where(
            DailyTrainerSummary.trainer_id == world.trainer.id, DailyTrainerSummary.summary_date == today
        )
    ).all()
    assert len(rows) == 1 and rows[0].puzzle_attempts == 3


def test_trainer_attendance_counts_by_session_day(api, world):
    past_day = world.sessions.past.start_time.date()
    summary_service.compute_day(world.db, past_day)

    row = world.db.scalar(
        select(DailyTrainerSummary).where(
            DailyTrainerSummary.trainer_id == world.trainer.id, DailyTrainerSummary.summary_date == past_day
        )
    )
    assert row.sessions_held == 1
    assert (row.attendance_present, row.attendance_absent) == (1, 1)


def test_admin_report_reads_precomputed_rows(api, world):
    admin = auth_headers(_user(world.db, "admin", "Admin"))
    today = today_utc()
    summary_service.compute_range(world.db, today - timedelta(days=6), today)

    report = api.get("/admin/reports/daily", params={"days": 7}, headers=admin)
    assert report.status_code == 200
    body = report.json()
    assert len(body["series"]) == 7 and body["missing_days"] == []
    assert all(point["computed"] for point in body["series"])

    stored = world.db.scalars(
        select(DailyPlatformSummary).where(DailyPlatformSummary.summary_date >= today - timedelta(days=6))
    ).all()
    assert body["totals"]["puzzle_attempts"] == sum(row.puzzle_attempts for row in stored)
    assert body["totals"]["sessions_held"] == sum(row.sessions_held for row in stored)

    trainer_row = next(t for t in body["trainers"] if t["trainer_id"] == str(world.trainer.id))
    assert trainer_row["sessions_held"] >= 1
    assert trainer_row["attendance_rate"] == 50.0


def test_report_lists_days_not_computed_yet(api, world):
    admin = auth_headers(_user(world.db, "admin", "Admin"))
    world.db.query(DailyPlatformSummary).filter(
        DailyPlatformSummary.summary_date == today_utc()
    ).delete()
    world.db.flush()

    body = api.get("/admin/reports/daily", params={"days": 7}, headers=admin).json()
    assert body["series"][-1]["computed"] is False
    assert today_utc().isoformat() in body["missing_days"]


def test_trainer_report_and_permissions(api, world):
    attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, ["g6g7"])
    summary_service.compute_day(world.db, today_utc())

    report = api.get("/trainer/reports/daily", params={"days": 7}, headers=world.trainer_headers)
    assert report.status_code == 200
    body = report.json()
    assert body["totals"]["puzzles_solved"] == 1
    names = {row["full_name"] for row in body["students"]}
    assert names == {"Student A", "Student B"}
    a_row = next(row for row in body["students"] if row["full_name"] == "Student A")
    assert a_row["active_days"] == 1 and a_row["puzzles_solved"] == 1

    assert api.get("/admin/reports/daily", headers=world.trainer_headers).status_code == 403
    assert api.get("/trainer/reports/daily", headers=world.headers["a"]).status_code == 403
    assert api.get("/admin/reports/daily", params={"days": 1000}, headers=world.trainer_headers).status_code in (403, 422)


def test_compute_range_limits():
    with pytest.raises(ValueError):
        summary_service.compute_range(None, today_utc(), today_utc() - timedelta(days=1))


# --- Lichess import --------------------------------------------------------------

ROW = {
    "PuzzleId": "zzT3st",
    "FEN": "r6k/pp2r2p/4Rp1Q/3p4/8/1N1P2R1/PqP2bPP/7K b - - 0 24",
    "Moves": "f2g3 e6e7 b2b1 b3c1 b1c1 h6c1",
    "Rating": "1819",
    "RatingDeviation": "77",
    "Popularity": "95",
    "Themes": "crushing hangingPiece long middlegame",
    "GameUrl": "https://lichess.org/game/787zsVup/black#48",
}


def test_lichess_row_conversion():
    data = lichess.convert(ROW)
    # The opponent's first move is applied; the student moves next.
    assert data["fen"].split()[1] == "w"
    assert data["solution"] == "e6e7 b2b1 b3c1 b1c1 h6c1"
    assert data["difficulty"] == "advanced"
    assert data["themes"] == ["hangingPiece", "middlegame"]
    assert lichess.theme_slug("hangingPiece") == "hanging-piece"
    assert lichess.theme_slug("mateIn2") == "checkmate"

    with pytest.raises(ValueError):
        lichess.convert({**ROW, "Moves": "a1a8 e6e7"})


def test_lichess_import_is_idempotent(world):
    db = world.db
    rows = [ROW, {**ROW, "PuzzleId": "zzBad1", "Moves": "a1a8 e6e7"}]

    first = lichess.import_rows(db, rows, limit=10)
    assert first["imported"] == 1 and first["skipped_invalid"] == 1

    second = lichess.import_rows(db, rows, limit=10)
    assert second["imported"] == 0 and second["skipped_existing"] == 1

    puzzle = db.scalar(select(Puzzle).where(Puzzle.lichess_id == "zzT3st"))
    assert puzzle.source == "lichess" and puzzle.status == "published" and puzzle.rating == 1819
