import secrets
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.main import app
from app.models import (
    PuzzleAttempt,
    SessionAttendance,
    StudentBadge,
    StudentProgress,
    User,
)
from app.services.streak_service import active_streak, calculate_streaks
from scripts import seed
from tests.conftest import auth_headers
from tests.student_world import _user, api, attempt, tx_db, world  # noqa: F401

STUDENT_GET_PATHS = [
    "/student/dashboard",
    "/student/profile",
    "/student/groups",
    "/student/assignments",
    "/student/sessions",
    "/student/attendance",
    "/student/gamification",
    "/student/badges",
    "/student/progress",
    "/student/activity",
]


def ids(items):
    return {item["id"] for item in items}


# --- Authentication and roles ------------------------------------------------


@pytest.mark.parametrize("path", STUDENT_GET_PATHS)
def test_missing_or_invalid_token_is_401(api, path):
    assert api.get(path).status_code == 401
    bad = api.get(path, headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401


@pytest.mark.parametrize("path", STUDENT_GET_PATHS)
def test_trainer_and_admin_get_403(api, world, path):
    admin = _user(world.db, "admin", "Admin")

    assert api.get(path, headers=world.trainer_headers).status_code == 403
    assert api.get(path, headers=auth_headers(admin)).status_code == 403


def test_student_without_profile_gets_clear_404(api, tx_db):
    user = _user(tx_db, "student", "New Student")
    headers = auth_headers(user)

    response = api.get("/student/dashboard", headers=headers)
    assert response.status_code == 404
    assert "profile" in response.json()["detail"]

    # The account itself is still viewable.
    profile = api.get("/student/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["student"] is None


def test_student_cannot_reach_trainer_or_admin_routes(api, world):
    paths = [
        path
        for path, methods in app.openapi()["paths"].items()
        if path.startswith(("/trainer", "/admin")) and "{" not in path and "get" in methods
    ]

    if not paths:
        pytest.skip("No Trainer/Admin GET routes are mounted yet.")

    for path in paths:
        assert api.get(path, headers=world.headers["a"]).status_code == 403, path


# --- Dashboard ---------------------------------------------------------------


def test_dashboard_counts_are_student_specific(api, world):
    attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, ["g6g7"])
    attempt(api, world, "a", world.puzzles.pin, world.assignments.shared, ["f1e2"])

    body = api.get("/student/dashboard", headers=world.headers["a"]).json()

    # Visible to A: shared, overdue, invalid, closed (not draft, future or B's).
    counts = body["assignment_counts"]
    assert counts["total"] == 4
    assert counts["in_progress"] == 1  # shared
    assert counts["overdue"] == 1
    assert counts["pending"] == 2  # invalid + closed
    assert counts["completed"] == 0

    stats = body["stats"]
    assert stats["puzzles_solved"] == 1
    assert stats["total_attempts"] == 2
    assert stats["accuracy_percent"] == 50.0
    assert stats["badges_earned"] == 1
    assert stats["current_streak"] == 1
    assert len(body["recent_attempts"]) == 2

    assert body["trainer"]["full_name"] == "Test Trainer"
    assert [g["name"] for g in body["groups"]] == ["M6 Test Group"]
    assert ids(body["upcoming_sessions"]) == {str(world.sessions.upcoming.id)}
    assert body["next_milestone"]["badge_code"] == "three-puzzles-solved"

    # B's view is unaffected by A's work.
    other = api.get("/student/dashboard", headers=world.headers["b"]).json()
    assert other["stats"]["total_attempts"] == 0
    assert other["stats"]["total_xp"] == 0
    assert other["recent_attempts"] == []
    assert str(world.sessions.b_private.id) in ids(other["upcoming_sessions"])


def test_dashboard_matches_seeded_demo_records(api, tx_db):
    seed.seed_all(tx_db, hash_password(secrets.token_urlsafe(16)))
    student = seed.get_student_profile(tx_db, "student1@chessacademy.local")
    user = tx_db.get(User, student.user_id)

    body = api.get("/student/dashboard", headers=auth_headers(user)).json()

    progress = tx_db.scalar(
        select(StudentProgress).where(StudentProgress.student_id == student.id)
    )
    attempts = tx_db.scalar(
        select(func.count(PuzzleAttempt.id)).where(PuzzleAttempt.student_id == student.id)
    )
    badges = tx_db.scalar(
        select(func.count(StudentBadge.id)).where(StudentBadge.student_id == student.id)
    )

    assert body["stats"]["total_xp"] == progress.total_xp
    assert body["stats"]["total_attempts"] == attempts
    assert body["stats"]["badges_earned"] == badges
    assert seed.DEMO_GROUP_NAME in [g["name"] for g in body["groups"]]


# --- Assignments -------------------------------------------------------------


def test_assignment_list_shows_only_visible_recipient_assignments(api, world):
    body = api.get("/student/assignments", headers=world.headers["a"]).json()
    titles = {item["title"] for item in body["items"]}

    assert titles == {"Shared tactics", "Overdue set", "Broken puzzle set", "Closed set"}
    assert body["total"] == 4

    b_titles = {
        item["title"]
        for item in api.get("/student/assignments", headers=world.headers["b"]).json()["items"]
    }
    assert b_titles == {"Shared tactics", "Only for B"}


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("overdue", {"Overdue set"}),
        ("pending", {"Shared tactics", "Broken puzzle set", "Closed set"}),
        ("completed", set()),
    ],
)
def test_assignment_status_filter(api, world, status, expected):
    response = api.get(
        "/student/assignments", params={"status": status}, headers=world.headers["a"]
    )
    assert {item["title"] for item in response.json()["items"]} == expected


def test_invalid_status_filter_is_422(api, world):
    response = api.get(
        "/student/assignments", params={"status": "done"}, headers=world.headers["a"]
    )
    assert response.status_code == 422


def test_assignment_pagination(api, world):
    first = api.get(
        "/student/assignments", params={"page_size": 3}, headers=world.headers["a"]
    ).json()
    second = api.get(
        "/student/assignments", params={"page_size": 3, "page": 2}, headers=world.headers["a"]
    ).json()

    assert (first["total"], first["pages"], len(first["items"])) == (4, 2, 3)
    assert len(second["items"]) == 1
    assert not ids(first["items"]) & ids(second["items"])


def test_cross_student_assignment_access_is_denied(api, world):
    b_only = world.assignments.b_only.id

    for path in (
        f"/student/assignments/{b_only}",
        f"/student/assignments/{b_only}/progress",
        f"/student/assignments/{b_only}/puzzles",
        f"/student/assignments/{world.assignments.draft.id}",
        f"/student/assignments/{uuid.uuid4()}",
    ):
        response = api.get(path, headers=world.headers["a"])
        assert response.status_code == 404, path
        assert response.json() == {"detail": "Assignment not found."}


def test_assignment_detail_and_progress_follow_attempts(api, world):
    a = world.assignments.shared
    attempt(api, world, "a", world.puzzles.mate, a, ["g6g7"])
    attempt(api, world, "a", world.puzzles.pin, a, ["f1e2"])

    detail = api.get(f"/student/assignments/{a.id}", headers=world.headers["a"]).json()

    assert detail["description"] == "Shared tactics instructions."
    assert detail["status"] == "in_progress"
    assert [p["status"] for p in detail["puzzles"]] == ["solved", "attempted", "not_started"]
    assert detail["puzzles"][0]["themes"] == ["M6 Test Theme"]

    progress = api.get(
        f"/student/assignments/{a.id}/progress", headers=world.headers["a"]
    ).json()
    assert progress == {
        **progress,
        "total_puzzles": 3,
        "completed_puzzles": 1,
        "remaining_puzzles": 2,
        "completion_percent": 33.3,
        "total_points": 6,
        "earned_points": 1,
        "attempts": 2,
    }

    # B shares the assignment but has made no progress in it.
    b_progress = api.get(
        f"/student/assignments/{a.id}/progress", headers=world.headers["b"]
    ).json()
    assert b_progress["completed_puzzles"] == 0 and b_progress["attempts"] == 0


def test_overdue_assignment_stays_overdue_until_completed(api, world):
    overdue = world.assignments.overdue
    path = f"/student/assignments/{overdue.id}"

    assert api.get(path, headers=world.headers["a"]).json()["status"] == "overdue"

    # Late work is accepted and completes the assignment.
    attempt(api, world, "a", world.puzzles.skewer, overdue, ["a1a6", "a6h6"])
    assert api.get(path, headers=world.headers["a"]).json()["status"] == "completed"


def test_students_cannot_modify_assignments(api, world):
    path = f"/student/assignments/{world.assignments.shared.id}"

    for method in ("put", "patch", "delete"):
        response = getattr(api, method)(path, headers=world.headers["a"])
        assert response.status_code == 405, method


# --- Groups ------------------------------------------------------------------


def test_groups_hide_other_students(api, world):
    body = api.get("/student/groups", headers=world.headers["a"]).json()

    assert body["total"] == 1
    group = body["items"][0]
    assert group["member_count"] == 2
    assert group["trainer"]["specialization"] == "Tactics"
    assert "members" not in group

    detail = api.get(f"/student/groups/{world.group.id}", headers=world.headers["a"]).json()
    assert ids(detail["upcoming_sessions"]) == {str(world.sessions.upcoming.id)}
    assert ids(detail["recent_sessions"]) == {str(world.sessions.past.id)}
    assert {a["title"] for a in detail["assignments"]} == {"Shared tactics"}


def test_non_member_group_is_404(api, world):
    outsider = _user(world.db, "student", "Outsider")
    from app.models import StudentProfile

    world.db.add(StudentProfile(user_id=outsider.id, trainer_id=world.trainer.id))
    world.db.flush()

    response = api.get(f"/student/groups/{world.group.id}", headers=auth_headers(outsider))
    assert response.status_code == 404


# --- Sessions and attendance -------------------------------------------------


def test_session_visibility(api, world):
    a_sessions = api.get("/student/sessions", headers=world.headers["a"]).json()
    assert ids(a_sessions["items"]) == {
        str(world.sessions.upcoming.id),
        str(world.sessions.past.id),
    }

    upcoming = api.get(
        "/student/sessions", params={"scope": "upcoming"}, headers=world.headers["a"]
    ).json()
    assert ids(upcoming["items"]) == {str(world.sessions.upcoming.id)}

    past = api.get(
        "/student/sessions", params={"scope": "past"}, headers=world.headers["a"]
    ).json()
    assert past["items"][0]["attendance_status"] == "present"

    b_sessions = api.get("/student/sessions", headers=world.headers["b"]).json()
    assert str(world.sessions.b_private.id) in ids(b_sessions["items"])


def test_session_detail_is_limited_to_participants(api, world):
    own = api.get(f"/student/sessions/{world.sessions.past.id}", headers=world.headers["a"])
    assert own.status_code == 200
    assert own.json()["attendance_status"] == "present"
    assert own.json()["meeting_url"] == "https://meet.example.com/class"

    other = api.get(
        f"/student/sessions/{world.sessions.b_private.id}", headers=world.headers["a"]
    )
    assert other.status_code == 404


def test_attendance_shows_only_own_records(api, world):
    body = api.get("/student/attendance", headers=world.headers["a"]).json()

    assert body["total"] == 1
    assert body["items"][0]["status"] == "present"
    assert body["summary"]["present"] == 1
    assert body["summary"]["attendance_rate_percent"] == 100.0
    assert "Private note for B" not in str(body)

    b_body = api.get("/student/attendance", headers=world.headers["b"]).json()
    assert b_body["summary"]["absent"] == 1
    assert b_body["summary"]["scheduled"] == 1
    assert b_body["summary"]["attendance_rate_percent"] == 0.0


def test_students_cannot_modify_attendance(api, world):
    session_path = f"/student/sessions/{world.sessions.past.id}"

    for method, path in (
        ("post", "/student/attendance"),
        ("patch", "/student/attendance"),
        ("patch", session_path),
        ("put", session_path),
        ("delete", session_path),
    ):
        response = getattr(api, method)(path, headers=world.headers["a"])
        assert response.status_code == 405, (method, path)

    stored = world.db.scalar(
        select(SessionAttendance.status).where(
            SessionAttendance.session_id == world.sessions.past.id,
            SessionAttendance.student_id == world.students["a"].id,
        )
    )
    assert stored == "present"


# --- Gamification and progress -----------------------------------------------


def test_gamification_totals_and_badges(api, world):
    attempt(api, world, "a", world.puzzles.mate, world.assignments.shared, ["g6g7"])

    body = api.get("/student/gamification", headers=world.headers["a"]).json()

    assert body["total_xp"] == sum(event["points"] for event in body["recent_xp"])
    assert body["puzzles_solved"] == 1
    assert body["current_streak"] == 1
    assert body["badges_earned"] == 1
    assert body["next_milestone"]["current"] == 1
    assert body["next_milestone"]["target"] == 3

    badges = api.get("/student/badges", headers=world.headers["a"]).json()
    earned = {badge["code"] for badge in badges if badge["earned"]}
    assert earned == {"first-puzzle-solved"}
    assert {"three-puzzles-solved", "first-game-played"} <= {b["code"] for b in badges}

    # B has earned nothing.
    b_badges = api.get("/student/badges", headers=world.headers["b"]).json()
    assert not any(badge["earned"] for badge in b_badges)


def test_no_endpoint_lets_students_award_rewards(api, world):
    for path in ("/student/gamification", "/student/badges", "/student/progress"):
        for method in ("post", "patch", "put"):
            response = getattr(api, method)(
                path, json={"total_xp": 9999}, headers=world.headers["a"]
            )
            assert response.status_code == 405, (method, path)

    body = api.get("/student/gamification", headers=world.headers["a"]).json()
    assert body["total_xp"] == 0


def test_progress_metrics(api, world):
    a = world.assignments.shared
    attempt(api, world, "a", world.puzzles.mate, a, ["g6g7"], time_taken_seconds=10)
    attempt(api, world, "a", world.puzzles.pin, a, ["f1e2"], time_taken_seconds=40)
    attempt(api, world, "a", world.puzzles.pin, a, ["f1c4", "b3c4"], time_taken_seconds=30)

    body = api.get("/student/progress", headers=world.headers["a"]).json()

    assert body["puzzles_attempted"] == 2
    assert body["puzzles_solved"] == 2
    assert body["total_attempts"] == 3
    assert body["accuracy_percent"] == 66.7
    assert body["average_solve_time_seconds"] == 20.0
    assert body["assignments_total"] == 4
    assert body["assignments_completed"] == 0
    assert body["daily"][-1]["puzzles_attempted"] == 3
    assert body["themes"] == [
        {
            "label": "M6 Test Theme",
            "attempts": 3,
            "solved_attempts": 2,
            "puzzles_solved": 2,
            "accuracy_percent": 66.7,
        }
    ]
    assert {d["label"] for d in body["difficulties"]} == {"beginner"}
    assert "accuracy_percent" in body["metric_definitions"]

    activity = api.get("/student/activity", headers=world.headers["a"]).json()
    assert activity["total"] == 3
    assert activity["items"][0]["assignment_title"] == "Shared tactics"

    empty = api.get("/student/progress", headers=world.headers["b"]).json()
    assert empty["total_attempts"] == 0 and empty["accuracy_percent"] is None


def test_streak_calculations():
    today = date(2026, 11, 2)
    run = [today - timedelta(days=n) for n in (0, 1, 2, 5, 6)]

    assert calculate_streaks(run) == (3, 3)
    assert active_streak(run, today) == 3
    assert active_streak([today - timedelta(days=1)], today) == 1
    assert active_streak([today - timedelta(days=2)], today) == 0
    assert active_streak([], today) == 0


# --- Profile -----------------------------------------------------------------


def test_profile_view_excludes_sensitive_fields(api, world):
    body = api.get("/student/profile", headers=world.headers["a"]).json()

    assert body["account"]["role"] == "student"
    assert body["student"]["chess_rating"] == 900
    assert body["trainer"]["full_name"] == "Test Trainer"
    assert [g["name"] for g in body["groups"]] == ["M6 Test Group"]

    text = str(body)
    for secret in ("password", "hash", "token", "notes", "settings"):
        assert secret not in text


def test_profile_update_allows_permitted_fields(api, world):
    response = api.patch(
        "/student/profile",
        json={
            "full_name": "  Renamed Student ",
            "phone": "+91 98765 43210",
            "language": "ta",
            "avatar_url": "https://example.com/me.png",
            "date_of_birth": "2010-05-01",
        },
        headers=world.headers["a"],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["full_name"] == "Renamed Student"
    assert body["account"]["language"] == "ta"
    assert body["student"]["date_of_birth"] == "2010-05-01"


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "admin"},
        {"is_active": False},
        {"is_verified": True},
        {"email": "new@example.com"},
        {"chess_rating": 2800},
        {"trainer_id": str(uuid.uuid4())},
        {"full_name": None},
        {"avatar_url": "javascript:alert(1)"},
        {"date_of_birth": "2999-01-01"},
    ],
)
def test_profile_update_rejects_forbidden_fields(api, world, payload):
    response = api.patch("/student/profile", json=payload, headers=world.headers["a"])

    assert response.status_code == 422

    user = world.db.get(User, world.users["a"].id)
    world.db.refresh(user)
    assert user.role == "student" and user.is_active
