"""Trainer session scheduling and attendance."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import SessionAttendance
from tests.trainer_fixtures import *  # noqa: F401,F403
from tests.trainer_fixtures import headers, now


@pytest.fixture()
def setup(factory):
    user, trainer = factory.trainer()
    students = [factory.student(trainer, name) for name in ("Ann", "Ben")]
    group = factory.group(trainer, students)
    return user, trainer, group, students


def session_payload(group, start=None, hours=1, **overrides):
    start = start or now() + timedelta(days=2)
    return {
        "group_id": str(group.id),
        "title": "Endgame fundamentals",
        "learning_objective": "Lucena position",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=hours)).isoformat(),
        **overrides,
    }


def test_schedule_valid_session(api, setup):
    user, _, group, _ = setup

    response = api.post("/trainer/sessions", json=session_payload(group), headers=headers(user))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["learning_objective"] == "Lucena position"
    assert body["roster_size"] == 2
    assert body["can_edit"] is True
    assert body["can_record_attendance"] is False
    assert body["attendance_summary"]["unrecorded"] == 2


def test_reject_invalid_time_ranges(api, setup):
    user, _, group, _ = setup
    start = now() + timedelta(days=1)

    zero_length = session_payload(group, start, hours=0)
    reversed_range = session_payload(group, start, hours=-1)
    in_past = session_payload(group, now() - timedelta(days=1))
    naive = session_payload(group, start, start_time="2030-01-01T10:00:00")

    for body in (zero_length, reversed_range, in_past, naive):
        assert api.post("/trainer/sessions", json=body, headers=headers(user)).status_code == 422, body


def test_reject_overlapping_sessions(api, setup):
    user, _, group, _ = setup
    start = now() + timedelta(days=3)

    assert api.post("/trainer/sessions", json=session_payload(group, start, 2), headers=headers(user)).status_code == 201
    overlap = api.post(
        "/trainer/sessions", json=session_payload(group, start + timedelta(hours=1)), headers=headers(user)
    )

    assert overlap.status_code == 409


def test_prevent_unauthorized_group_scheduling(api, factory, setup):
    user, _, _, _ = setup
    _, other = factory.trainer()
    foreign = factory.group(other)

    assert api.post("/trainer/sessions", json=session_payload(foreign), headers=headers(user)).status_code == 404


def test_other_trainer_cannot_manage_session(api, factory, setup):
    user, trainer, group, students = setup
    session = factory.session(trainer, group, now() - timedelta(hours=2))
    other_user, _ = factory.trainer()
    body = {"records": [{"student_id": str(students[0].id), "status": "present"}]}

    assert api.get(f"/trainer/sessions/{session.id}", headers=headers(other_user)).status_code == 404
    assert api.post(
        f"/trainer/sessions/{session.id}/attendance", json=body, headers=headers(other_user)
    ).status_code == 404


def test_edit_and_cancel_upcoming_session(api, setup):
    user, _, group, _ = setup
    created = api.post("/trainer/sessions", json=session_payload(group), headers=headers(user)).json()
    url = f"/trainer/sessions/{created['id']}"

    edited = api.patch(url, json={"title": "Rook endgames"}, headers=headers(user))
    bad_range = api.patch(
        url, json={"end_time": (now() + timedelta(days=1)).isoformat()}, headers=headers(user)
    )
    cancelled = api.post(f"{url}/cancel", headers=headers(user))
    edit_cancelled = api.patch(url, json={"title": "Too late"}, headers=headers(user))

    assert edited.json()["title"] == "Rook endgames"
    assert bad_range.status_code == 422
    assert cancelled.json()["status"] == "cancelled"
    assert edit_cancelled.status_code == 409


def test_record_attendance(api, factory, setup):
    user, trainer, group, (ann, ben) = setup
    session = factory.session(trainer, group, now() - timedelta(hours=1))

    response = api.post(
        f"/trainer/sessions/{session.id}/attendance",
        json={"records": [
            {"student_id": str(ann.id), "status": "present"},
            {"student_id": str(ben.id), "status": "late", "remarks": "10 minutes"},
        ]},
        headers=headers(user),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["attendance_summary"] == {"present": 1, "absent": 0, "late": 1, "excused": 0, "unrecorded": 0}
    assert {r["full_name"]: r["attendance_status"] for r in body["roster"]} == {"Ann": "present", "Ben": "late"}

    completed = api.post(f"/trainer/sessions/{session.id}/complete", headers=headers(user))
    assert completed.json()["status"] == "completed"


def test_prevent_duplicate_attendance(api, tdb, factory, setup):
    user, trainer, group, (ann, _) = setup
    session = factory.session(trainer, group, now() - timedelta(hours=1))
    url = f"/trainer/sessions/{session.id}/attendance"

    duplicate = api.post(url, json={"records": [
        {"student_id": str(ann.id), "status": "present"},
        {"student_id": str(ann.id), "status": "absent"},
    ]}, headers=headers(user))
    first = api.post(url, json={"records": [{"student_id": str(ann.id), "status": "absent"}]}, headers=headers(user))
    second = api.post(url, json={"records": [{"student_id": str(ann.id), "status": "excused"}]}, headers=headers(user))

    assert duplicate.status_code == 422
    assert first.status_code == second.status_code == 200
    count = tdb.scalar(
        select(func.count()).select_from(SessionAttendance).where(SessionAttendance.session_id == session.id)
    )
    assert count == 1
    assert {r["full_name"]: r["attendance_status"] for r in second.json()["roster"]}["Ann"] == "excused"


def test_attendance_rules(api, factory, setup):
    user, trainer, group, (ann, _) = setup
    future = factory.session(trainer, group, now() + timedelta(days=1))
    cancelled = factory.session(trainer, group, now() - timedelta(days=1), status="cancelled")
    started = factory.session(trainer, group, now() - timedelta(days=2))
    outsider = factory.student(trainer, "Not in group")
    body = {"records": [{"student_id": str(ann.id), "status": "present"}]}

    assert api.post(f"/trainer/sessions/{future.id}/attendance", json=body, headers=headers(user)).status_code == 409
    assert api.post(f"/trainer/sessions/{cancelled.id}/attendance", json=body, headers=headers(user)).status_code == 409
    assert api.post(
        f"/trainer/sessions/{started.id}/attendance",
        json={"records": [{"student_id": str(outsider.id), "status": "present"}]},
        headers=headers(user),
    ).status_code == 422
    assert api.post(
        f"/trainer/sessions/{started.id}/attendance",
        json={"records": [{"student_id": str(ann.id), "status": "scheduled"}]},
        headers=headers(user),
    ).status_code == 422


def test_session_list_scopes(api, factory, setup):
    user, trainer, group, _ = setup
    upcoming = factory.session(trainer, group, now() + timedelta(days=1))
    past = factory.session(trainer, group, now() - timedelta(days=1), status="completed")

    up = api.get("/trainer/sessions", params={"scope": "upcoming"}, headers=headers(user)).json()
    old = api.get("/trainer/sessions", params={"scope": "past"}, headers=headers(user)).json()

    assert [s["id"] for s in up["items"]] == [str(upcoming.id)]
    assert [s["id"] for s in old["items"]] == [str(past.id)]
