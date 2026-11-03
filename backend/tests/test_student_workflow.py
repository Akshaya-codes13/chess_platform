"""M6/M8/M10 end to end: hints, stored moves, assignment completion XP,
levels and badges, trainer review and resubmission."""

from sqlalchemy import select

from app.models import Notification, PuzzleAttempt, Submission, XPEvent
from app.services.xp_service import ASSIGNMENT_COMPLETED_XP, level_for_xp
from tests.student_world import *  # noqa: F401,F403
from tests.student_world import attempt


def hint(api, world, student, puzzle, assignment, moves=(), level=1):
    return api.post(
        f"/student/puzzles/{puzzle.id}/hint",
        json={"assignment_id": str(assignment.id), "moves": list(moves), "level": level},
        headers=world.headers[student],
    )


def solve_shared(api, world, student="a"):
    """Solve every puzzle of the shared assignment; return the last response."""
    shared, puzzles = world.assignments.shared, world.puzzles
    assert attempt(api, world, student, puzzles.mate, shared, ["g6g7"]).json()["status"] == "solved"
    assert attempt(api, world, student, puzzles.pin, shared, ["f1c4"]).json()["status"] == "in_progress"
    assert attempt(api, world, student, puzzles.pin, shared, ["f1c4", "b3c4"]).json()["status"] == "solved"
    return attempt(api, world, student, puzzles.skewer, shared, ["a1a6", "a6h6"])


# --- Hints and stored moves ----------------------------------------------------


def test_hint_levels(api, world):
    shared, pin = world.assignments.shared, world.puzzles.pin

    first = hint(api, world, "a", pin, shared)
    assert first.status_code == 200
    assert first.json() == {"level": 1, "from_square": "f1", "piece": "bishop", "move": None, "san": None}

    reveal = hint(api, world, "a", pin, shared, level=2).json()
    assert reveal["move"] == "f1c4" and reveal["san"] == "Bc4"

    # After the correct first move, the hint is for the second student move.
    assert hint(api, world, "a", pin, shared, ["f1c4"], level=2).json()["move"] == "b3c4"


def test_hint_rejects_finished_or_foreign_attempts(api, world):
    shared, pin = world.assignments.shared, world.puzzles.pin

    assert hint(api, world, "a", pin, shared, ["f1e2"]).status_code == 422
    assert hint(api, world, "a", world.puzzles.unassigned, shared).status_code == 404
    assert hint(api, world, "a", world.puzzles.mate, world.assignments.b_only).status_code == 404


def test_attempt_stores_moves_and_hints(api, world):
    shared, pin = world.assignments.shared, world.puzzles.pin

    response = attempt(api, world, "a", pin, shared, ["f1c4", "b3c4"], hints_used=2, time_taken_seconds=40)
    assert response.json()["status"] == "solved"

    stored = world.db.get(PuzzleAttempt, response.json()["attempt_id"])
    assert stored.moves == ["f1c4", "b3c4"]
    assert stored.hints_used == 2
    assert stored.time_taken_seconds == 40
    assert stored.attempted_at is not None


def test_failed_attempt_stores_wrong_move(api, world):
    response = attempt(api, world, "a", world.puzzles.pin, world.assignments.shared, ["f1e2"])
    assert response.json()["status"] == "failed"
    assert world.db.get(PuzzleAttempt, response.json()["attempt_id"]).moves == ["f1e2"]


# --- Completion XP, badges, level ----------------------------------------------


def test_completing_assignment_awards_xp_badges_and_level(api, world):
    last = solve_shared(api, world).json()

    assert last["assignment_completed_now"] is True
    codes = {badge["code"] for badge in last["badges_awarded"]}
    assert {"three-puzzles-solved", "first-assignment-completed"} <= codes

    student = world.students["a"]
    events = world.db.scalars(select(XPEvent).where(XPEvent.student_id == student.id)).all()
    assignment_events = [e for e in events if e.source_type == "assignment"]
    assert len(assignment_events) == 1 and assignment_events[0].points == ASSIGNMENT_COMPLETED_XP

    summary = api.get("/student/gamification", headers=world.headers["a"]).json()
    assert summary["total_xp"] == sum(e.points for e in events)
    assert summary["assignments_completed"] == 1
    assert summary["xp_level"] == level_for_xp(summary["total_xp"])
    assert summary["xp_level"]["level"] >= 2
    assert summary["active_days"] == 1
    assert summary["activity_calendar"][-1]["puzzles_solved"] == 3

    # Re-solving after completion awards nothing more.
    again = attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, ["g6g7"]).json()
    assert again["xp_awarded"] == 0 and again["assignment_completed_now"] is False


def test_trainer_is_notified_of_completion(api, world):
    solve_shared(api, world)
    notes = world.db.scalars(
        select(Notification).where(Notification.user_id == world.trainer_user.id)
    ).all()
    assert [n.notification_type for n in notes] == ["assignment_completed"]


def test_level_thresholds():
    assert level_for_xp(0)["level"] == 1
    assert level_for_xp(49)["level"] == 1
    assert level_for_xp(50)["level"] == 2
    assert level_for_xp(2250)["level"] == 10
    assert level_for_xp(2750)["level"] == 11
    assert level_for_xp(100)["xp_to_next_level"] == 50


# --- Review and resubmission ---------------------------------------------------


def test_trainer_reviews_submission(api, world):
    solve_shared(api, world)
    shared, student = world.assignments.shared, world.students["a"]
    base = f"/trainer/assignments/{shared.id}/submissions/{student.id}"

    detail = api.get(base, headers=world.trainer_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["submission"]["status"] == "submitted"
    assert body["earned_points"] == body["total_points"] == 6
    pin_item = next(p for p in body["puzzles"] if p["puzzle_id"] == str(world.puzzles.pin.id))
    assert pin_item["attempts"][0]["moves"] == ["f1c4", "b3c4"]

    too_high = api.post(f"{base}/review", json={"status": "graded", "score": 99}, headers=world.trainer_headers)
    assert too_high.status_code == 422

    graded = api.post(
        f"{base}/review", json={"status": "graded", "score": 5, "feedback": "Great work"},
        headers=world.trainer_headers,
    )
    assert graded.status_code == 200
    assert graded.json()["submission"] == {**graded.json()["submission"], "status": "graded", "score": 5}

    student_view = api.get(f"/student/assignments/{shared.id}", headers=world.headers["a"]).json()
    assert student_view["submission"]["trainer_feedback"] == "Great work"

    progress = api.get(f"/trainer/assignments/{shared.id}/progress", headers=world.trainer_headers).json()
    row = next(r for r in progress["recipients"] if r["student_id"] == str(student.id))
    assert row["submission_status"] == "graded" and row["trainer_feedback"] == "Great work"

    note = world.db.scalar(
        select(Notification).where(
            Notification.user_id == world.users["a"].id,
            Notification.notification_type == "submission_reviewed",
        )
    )
    assert note is not None


def test_review_requires_submission_and_recipient(api, world):
    shared = world.assignments.shared
    url = f"/trainer/assignments/{shared.id}/submissions/{world.students['a'].id}/review"
    assert api.post(url, json={"status": "graded"}, headers=world.trainer_headers).status_code == 409

    stranger = f"/trainer/assignments/{world.assignments.b_only.id}/submissions/{world.students['a'].id}"
    assert api.get(stranger, headers=world.trainer_headers).status_code == 404

    # Students cannot use trainer routes.
    assert api.get(url.removesuffix("/review"), headers=world.headers["a"]).status_code == 403


def test_partial_submit_and_resubmit_after_return(api, world):
    overdue, student = world.assignments.overdue, world.students["a"]
    url = f"/student/assignments/{overdue.id}/submit"

    assert api.post(url, headers=world.headers["a"]).status_code == 422  # nothing attempted yet

    assert attempt(api, world, "a", world.puzzles.skewer, overdue, ["a1b1"]).json()["status"] == "failed"
    first = api.post(url, headers=world.headers["a"])
    assert first.status_code == 200
    assert first.json()["submission"]["attempt_number"] == 1
    assert first.json()["submission"]["score"] == 0

    assert api.post(url, headers=world.headers["a"]).status_code == 409

    review = f"/trainer/assignments/{overdue.id}/submissions/{student.id}/review"
    assert api.post(review, json={"status": "returned", "feedback": "Try again"}, headers=world.trainer_headers).status_code == 200

    second = api.post(url, headers=world.headers["a"])
    assert second.status_code == 200
    assert second.json()["submission"]["attempt_number"] == 2

    assert world.db.scalar(
        select(Submission.status).where(Submission.assignment_id == overdue.id, Submission.attempt_number == 1)
    ) == "returned"


def test_cannot_submit_hidden_or_closed_assignments(api, world):
    assert api.post(f"/student/assignments/{world.assignments.b_only.id}/submit", headers=world.headers["a"]).status_code == 404
    assert api.post(f"/student/assignments/{world.assignments.closed.id}/submit", headers=world.headers["a"]).status_code == 409
