import uuid
from types import SimpleNamespace

import chess
import pytest
from sqlalchemy import func, select

from app.models import (
    DailyActivity,
    PuzzleAttempt,
    StudentBadge,
    StudentProgress,
    Submission,
    XPEvent,
)
from app.services import puzzle_solver
from app.services.xp_service import PUZZLE_SOLVED_XP
from tests.student_world import (  # noqa: F401  (fixtures)
    MATE_IN_ONE,
    PIN,
    api,
    attempt,
    tx_db,
    world,
)


def count(db, model, **filters):
    query = select(func.count()).select_from(model)
    for name, value in filters.items():
        query = query.where(getattr(model, name) == value)
    return db.scalar(query)


# --- Solver: pure python-chess validation ------------------------------------


def test_solver_solved_line_with_opponent_reply():
    result = puzzle_solver.check_line(*PIN, ["f1c4", "b3c4"])

    assert result.status == "solved"
    assert [m.by for m in result.played] == ["student", "opponent", "student"]
    assert [m.san for m in result.played] == ["Bc4", "Qxc4", "bxc4"]


def test_solver_correct_prefix_is_in_progress_with_reply():
    result = puzzle_solver.check_line(*PIN, ["f1c4"])

    assert result.status == "in_progress"
    assert result.played[-1].uci == "d5c4"
    assert result.board.turn == chess.WHITE


def test_solver_legal_but_wrong_move_fails():
    assert puzzle_solver.check_line(*PIN, ["f1e2"]).status == "failed"


def test_solver_accepts_alternative_checkmate():
    fen = "6k1/5ppp/8/8/8/8/8/R3R1K1 w - - 0 1"

    assert puzzle_solver.check_line(fen, "a1a8", ["e1e8"]).status == "solved"


@pytest.mark.parametrize("moves", [["e1g1"], ["h8h7"], ["a1a1"]])
def test_solver_rejects_illegal_moves(moves):
    with pytest.raises(puzzle_solver.IllegalMoveError):
        puzzle_solver.check_line(*MATE_IN_ONE, moves)


def test_solver_rejects_too_many_moves():
    with pytest.raises(puzzle_solver.IllegalMoveError):
        puzzle_solver.check_line(*MATE_IN_ONE, ["g6g7", "h8g7"])


def test_solver_enforces_check_restrictions():
    # The king on e1 is in check from e8, so a pawn move is illegal.
    fen = "4r1k1/8/8/8/8/8/P7/4K3 w - - 0 1"

    with pytest.raises(puzzle_solver.IllegalMoveError):
        puzzle_solver.check_line(fen, "e1d1", ["a2a3"])


def test_solver_castling_rules():
    board = chess.Board("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    assert {"e1g1", "e1c1"} <= set(puzzle_solver.legal_moves(board))

    # f1 is attacked by the rook on f8, so king-side castling is illegal.
    attacked = chess.Board("4kr2/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    assert "e1g1" not in puzzle_solver.legal_moves(attacked)
    assert "e1c1" in puzzle_solver.legal_moves(attacked)


def test_solver_en_passant():
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    assert "e5d6" in puzzle_solver.legal_moves(board)


def test_solver_promotion_piece_must_match():
    fen = "8/4P1k1/8/8/8/8/8/4K3 w - - 0 1"

    assert puzzle_solver.check_line(fen, "e7e8q", ["e7e8q"]).status == "solved"
    assert puzzle_solver.check_line(fen, "e7e8q", ["e7e8n"]).status == "failed"

    with pytest.raises(puzzle_solver.IllegalMoveError):
        puzzle_solver.check_line(fen, "e7e8q", ["e7e8"])  # promotion piece missing


def test_solver_reports_checkmate_and_stalemate():
    mated = puzzle_solver.check_line(*MATE_IN_ONE, ["g6g7"]).board
    assert puzzle_solver.position_state(mated)["is_checkmate"]

    stalemate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    state = puzzle_solver.position_state(stalemate)
    assert state["is_stalemate"] and state["legal_moves"] == []


@pytest.mark.parametrize(
    ("fen", "solution"),
    [
        ("not a fen", "e2e4"),
        ("8/8/8/8/8/8/8/8 w - - 0 1", "e2e4"),  # no kings
        (MATE_IN_ONE[0], ""),
        (MATE_IN_ONE[0], "e2e4"),  # illegal in the position
    ],
)
def test_solver_rejects_invalid_puzzle_data(fen, solution):
    with pytest.raises(puzzle_solver.InvalidPuzzleError):
        puzzle_solver.load_puzzle(fen, solution)


# --- Puzzle detail -----------------------------------------------------------


def test_puzzle_detail_hides_solution_and_lists_legal_moves(api, world):
    p, a = world.puzzles.pin, world.assignments.shared
    response = api.get(
        f"/student/puzzles/{p.id}",
        params={"assignment_id": str(a.id)},
        headers=world.headers["a"],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["orientation"] == "white"
    assert body["moves_required"] == 2
    assert body["position"]["fen"] == chess.Board(PIN[0]).fen()
    assert "f1c4" in body["position"]["legal_moves"]
    assert body["solution_san"] is None and body["explanation"] is None
    assert "solution" not in body
    assert body["previous_puzzle_id"] == str(world.puzzles.mate.id)
    assert body["next_puzzle_id"] == str(world.puzzles.skewer.id)


def test_puzzle_access_requires_a_visible_assignment(api, world):
    shared, b_only = world.assignments.shared, world.assignments.b_only
    cases = [
        (world.puzzles.unassigned, shared),  # not in that assignment
        (world.puzzles.mate, b_only),  # another student's assignment
        (world.puzzles.mate, world.assignments.draft),  # draft
        (world.puzzles.mate, world.assignments.future),  # not started yet
        (world.puzzles.mate, SimpleNamespace(id=uuid.uuid4())),  # nonexistent
    ]

    for puzzle, assignment in cases:
        response = api.get(
            f"/student/puzzles/{puzzle.id}",
            params={"assignment_id": str(assignment.id)},
            headers=world.headers["a"],
        )
        assert response.status_code == 404, assignment.id

        submitted = attempt(api, world, "a", puzzle, assignment, ["g6g7"])
        assert submitted.status_code == 404

    assert count(world.db, PuzzleAttempt, student_id=world.students["a"].id) == 0


def test_puzzle_detail_requires_assignment_id(api, world):
    response = api.get(
        f"/student/puzzles/{world.puzzles.mate.id}", headers=world.headers["a"]
    )
    assert response.status_code == 422


def test_invalid_puzzle_data_returns_422(api, world):
    p, a = world.puzzles.broken, world.assignments.invalid

    detail = api.get(
        f"/student/puzzles/{p.id}",
        params={"assignment_id": str(a.id)},
        headers=world.headers["a"],
    )
    assert detail.status_code == 422

    submitted = attempt(api, world, "a", p, a, ["e2e4"])
    assert submitted.status_code == 422
    assert count(world.db, PuzzleAttempt, puzzle_id=p.id) == 0


# --- Attempts ----------------------------------------------------------------


def test_correct_solution_records_attempt_and_awards_xp(api, world):
    student = world.students["a"]
    response = attempt(
        api, world, "a", world.puzzles.mate, world.assignments.shared,
        ["g6g7"], time_taken_seconds=12,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "solved" and body["recorded"]
    assert body["already_solved"] is False
    assert body["position"]["is_checkmate"]
    assert body["solution_san"] == ["Qg7#"]
    assert body["explanation"] == "Test explanation."

    # 10 XP for the solve plus the "first puzzle" badge reward.
    assert [b["code"] for b in body["badges_awarded"]] == ["first-puzzle-solved"]
    assert body["xp_awarded"] == PUZZLE_SOLVED_XP + body["badges_awarded"][0]["xp_reward"]

    db = world.db
    stored = db.scalar(select(PuzzleAttempt).where(PuzzleAttempt.student_id == student.id))
    assert stored.is_solved and stored.time_taken_seconds == 12
    assert stored.assignment_id == world.assignments.shared.id

    progress = db.scalar(select(StudentProgress).where(StudentProgress.student_id == student.id))
    events = db.scalars(select(XPEvent.points).where(XPEvent.student_id == student.id)).all()
    assert progress.total_xp == sum(events) == body["xp_awarded"]
    assert progress.puzzles_solved == 1
    assert progress.current_streak == 1

    daily = db.scalar(select(DailyActivity).where(DailyActivity.student_id == student.id))
    assert (daily.puzzles_attempted, daily.puzzles_solved, daily.xp_earned) == (
        1, 1, body["xp_awarded"],
    )

    assert body["assignment_progress"]["completed_puzzles"] == 1
    assert body["assignment_status"] == "in_progress"


def test_incorrect_move_records_failed_attempt_without_xp(api, world):
    response = attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, ["g6g8"])

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed" and body["recorded"]
    assert body["xp_awarded"] == 0
    assert body["solution_san"] is None

    student_id = world.students["a"].id
    assert count(world.db, PuzzleAttempt, student_id=student_id, is_solved=False) == 1
    assert count(world.db, XPEvent, student_id=student_id) == 0


def test_incomplete_solution_is_not_recorded(api, world):
    response = attempt(api, world, "a", world.puzzles.pin, world.assignments.shared, ["f1c4"])

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress" and not body["recorded"]
    assert [m["uci"] for m in body["played"]] == ["f1c4", "d5c4"]
    assert "b3c4" in body["position"]["legal_moves"]
    assert count(world.db, PuzzleAttempt, student_id=world.students["a"].id) == 0

    finished = attempt(
        api, world, "a", world.puzzles.pin, world.assignments.shared, ["f1c4", "b3c4"]
    )
    assert finished.json()["status"] == "solved"


@pytest.mark.parametrize("moves", [["e2e4"], ["g6g7", "h8g8"], ["Qg7"], []])
def test_illegal_or_malformed_moves_are_rejected(api, world, moves):
    response = attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, moves)

    assert response.status_code == 422
    assert count(world.db, PuzzleAttempt, student_id=world.students["a"].id) == 0


def test_repeated_solve_awards_no_duplicate_xp(api, world):
    first = attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, ["g6g7"])
    xp_after_first = first.json()["xp_awarded"]

    again = attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, ["g6g7"])
    body = again.json()

    assert body["status"] == "solved" and body["recorded"]
    assert body["already_solved"] is True
    assert body["xp_awarded"] == 0 and body["badges_awarded"] == []

    student_id = world.students["a"].id
    db = world.db
    assert count(db, PuzzleAttempt, student_id=student_id) == 2
    assert count(db, StudentBadge, student_id=student_id) == 1
    progress = db.scalar(select(StudentProgress).where(StudentProgress.student_id == student_id))
    assert progress.total_xp == xp_after_first
    assert progress.puzzles_solved == 1


def test_already_solved_puzzle_in_another_assignment_earns_no_xp(api, world):
    # Student B solves the mate in "Only for B", then again in the shared set.
    first = attempt(api, world, "b", world.puzzles.mate, world.assignments.b_only, ["g6g7"])
    assert first.json()["xp_awarded"] > 0

    second = attempt(api, world, "b", world.puzzles.mate, world.assignments.shared, ["g6g7"])
    assert second.json()["already_solved"] is True
    assert second.json()["xp_awarded"] == 0
    # It still counts toward the shared assignment's progress.
    assert second.json()["assignment_progress"]["completed_puzzles"] == 1


def test_completing_assignment_creates_one_submission(api, world):
    a = world.assignments.shared
    attempt(api, world, "a", world.puzzles.mate, a, ["g6g7"])
    attempt(api, world, "a", world.puzzles.pin, a, ["f1c4", "b3c4"])
    last = attempt(api, world, "a", world.puzzles.skewer, a, ["a1a6", "a6h6"]).json()

    assert last["assignment_status"] == "completed"
    assert last["assignment_completed_now"] is True
    assert last["assignment_progress"]["completion_percent"] == 100.0

    # The third solve also reaches the "three puzzles" badge.
    assert "three-puzzles-solved" in [b["code"] for b in last["badges_awarded"]]

    student_id = world.students["a"].id
    submission = world.db.scalar(
        select(Submission).where(
            Submission.assignment_id == a.id, Submission.student_id == student_id
        )
    )
    assert submission.status == "submitted"
    assert submission.score == 1 + 2 + 3  # points of every solved puzzle

    repeat = attempt(api, world, "a", world.puzzles.mate, a, ["g6g7"]).json()
    assert repeat["assignment_completed_now"] is False
    assert count(world.db, Submission, student_id=student_id) == 1


def test_attempt_cannot_set_its_own_result_or_xp(api, world):
    for extra in ({"is_solved": True}, {"xp": 1000}, {"points": 50}):
        response = attempt(
            api, world, "a", world.puzzles.mate, world.assignments.shared,
            ["g6g8"], **extra,
        )
        assert response.status_code == 422, extra

    assert count(world.db, PuzzleAttempt, student_id=world.students["a"].id) == 0
    assert count(world.db, XPEvent, student_id=world.students["a"].id) == 0


def test_closed_assignment_rejects_attempts(api, world):
    response = attempt(api, world, "a", world.puzzles.pin, world.assignments.closed, ["f1c4"])
    assert response.status_code == 409


def test_trainer_cannot_use_student_attempt_endpoint(api, world):
    response = api.post(
        f"/student/puzzles/{world.puzzles.mate.id}/attempts",
        json={"assignment_id": str(world.assignments.shared.id), "moves": ["g6g7"]},
        headers=world.trainer_headers,
    )
    assert response.status_code == 403
