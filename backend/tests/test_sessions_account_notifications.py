"""M5 account settings, M7 sessions for selected students and tabs, and
notifications for every role."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.models import Notification, RefreshToken
from tests.student_world import *  # noqa: F401,F403
from tests.student_world import _session


def schedule(api, world, **extra):
    start = datetime.now(timezone.utc) + timedelta(days=5)
    payload = {
        "group_id": str(world.group.id),
        "title": "Endgame clinic",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=1)).isoformat(),
        **extra,
    }
    return api.post("/trainer/sessions", json=payload, headers=world.trainer_headers)


def student_session_ids(api, world, key):
    items = api.get("/student/sessions?scope=upcoming", headers=world.headers[key]).json()["items"]
    return {item["id"] for item in items}


# --- Sessions ----------------------------------------------------------------


def test_group_session_is_visible_to_every_member_and_notifies(api, world):
    response = schedule(api, world)
    assert response.status_code == 201
    body = response.json()
    assert body["session_type"] == "group" and body["roster_size"] == 2

    for key in ("a", "b"):
        assert body["id"] in student_session_ids(api, world, key)
        note = world.db.scalar(
            select(Notification).where(
                Notification.user_id == world.users[key].id,
                Notification.notification_type == "session_scheduled",
            )
        )
        assert note is not None and note.data["session_id"] == body["id"]


def test_session_for_selected_students_only(api, world):
    a = world.students["a"]
    response = schedule(api, world, student_ids=[str(a.id)])
    assert response.status_code == 201
    body = response.json()
    assert body["session_type"] == "individual"
    assert body["roster_size"] == 1
    assert [entry["student_id"] for entry in body["roster"]] == [str(a.id)]

    assert body["id"] in student_session_ids(api, world, "a")
    assert body["id"] not in student_session_ids(api, world, "b")
    assert api.get(f"/student/sessions/{body['id']}", headers=world.headers["b"]).status_code == 404

    notified = set(
        world.db.scalars(
            select(Notification.user_id).where(Notification.notification_type == "session_scheduled")
        )
    )
    assert world.users["a"].id in notified and world.users["b"].id not in notified


def test_selected_students_must_be_group_members(api, world):
    # A random ID (here the trainer profile's) is not a member of the group.
    response = schedule(api, world, student_ids=[str(world.trainer.id)])
    assert response.status_code == 422

    duplicate = schedule(api, world, student_ids=[str(world.students["a"].id)] * 2)
    assert duplicate.status_code == 422


def test_cancel_notifies_invited_students(api, world):
    session_id = schedule(api, world, student_ids=[str(world.students["b"].id)]).json()["id"]
    assert api.post(f"/trainer/sessions/{session_id}/cancel", headers=world.trainer_headers).status_code == 200

    cancelled = world.db.scalars(
        select(Notification.user_id).where(Notification.notification_type == "session_cancelled")
    ).all()
    assert cancelled == [world.users["b"].id]


def test_active_and_completed_tabs(api, world):
    now = datetime.now(timezone.utc)
    live = _session(world.db, world.trainer, "Live class", now - timedelta(minutes=10), "scheduled", world.group)

    def ids(scope):
        response = api.get(f"/trainer/sessions?scope={scope}", headers=world.trainer_headers)
        assert response.status_code == 200
        return {item["id"] for item in response.json()["items"]}

    assert ids("active") == {str(live.id)}
    assert ids("completed") == {str(world.sessions.past.id)}
    assert str(world.sessions.upcoming.id) in ids("upcoming")
    assert str(live.id) not in ids("upcoming")

    listed = api.get("/trainer/sessions?scope=active", headers=world.trainer_headers).json()["items"][0]
    assert listed["is_active"] is True


def test_attendance_for_individual_session(api, world):
    b = world.students["b"]
    private = world.sessions.b_private
    private.start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    private.end_time = private.start_time + timedelta(hours=1)
    world.db.flush()

    ok = api.post(
        f"/trainer/sessions/{private.id}/attendance",
        json={"records": [{"student_id": str(b.id), "status": "present"}]},
        headers=world.trainer_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["attendance_summary"]["present"] == 1

    outsider = api.post(
        f"/trainer/sessions/{private.id}/attendance",
        json={"records": [{"student_id": str(world.students['a'].id), "status": "present"}]},
        headers=world.trainer_headers,
    )
    assert outsider.status_code == 422


# --- Account settings ----------------------------------------------------------


def test_settings_defaults_and_update_for_every_role(api, world):
    for headers in (world.headers["a"], world.trainer_headers):
        current = api.get("/account/settings", headers=headers)
        assert current.status_code == 200
        body = current.json()
        assert body["board"] == {"theme": "wood", "pieces": "classic", "show_coordinates": True}
        assert body["notifications"]["sessions"] is True and body["notifications"]["email"] is False

        updated = api.patch(
            "/account/settings",
            json={"language": "ta", "board": {"theme": "green"}, "notifications": {"content": False}},
            headers=headers,
        ).json()
        assert updated["language"] == "ta"
        assert updated["board"]["theme"] == "green" and updated["board"]["pieces"] == "classic"
        assert updated["notifications"]["content"] is False and updated["notifications"]["sessions"] is True


def test_settings_reject_unknown_values_and_fields(api, world):
    headers = world.headers["a"]
    assert api.patch("/account/settings", json={"board": {"theme": "neon"}}, headers=headers).status_code == 422
    assert api.patch("/account/settings", json={"role": "admin"}, headers=headers).status_code == 422
    assert api.patch("/account/settings", json={"settings": {"x": 1}}, headers=headers).status_code == 422
    assert api.patch("/account/settings", json={"language": "xx"}, headers=headers).status_code == 422
    assert api.get("/account/settings").status_code in (401, 403)


def test_disabled_category_suppresses_notifications(api, world):
    api.patch("/account/settings", json={"notifications": {"sessions": False}}, headers=world.headers["a"])
    schedule(api, world)

    a_notes = world.db.scalars(select(Notification).where(Notification.user_id == world.users["a"].id)).all()
    b_notes = world.db.scalars(select(Notification).where(Notification.user_id == world.users["b"].id)).all()
    assert a_notes == [] and len(b_notes) == 1


def test_change_password(api, world):
    user = world.users["a"]
    user.password_hash = hash_password("OldPassword1")
    world.db.add(
        RefreshToken(
            user_id=user.id,
            token_jti=f"test-jti-{user.id}",
            token_hash="not-a-real-token-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    world.db.flush()

    wrong = api.post("/account/password", json={"current_password": "nope", "new_password": "NewPassword2"}, headers=world.headers["a"])
    assert wrong.status_code == 422

    weak = api.post("/account/password", json={"current_password": "OldPassword1", "new_password": "short"}, headers=world.headers["a"])
    assert weak.status_code == 422

    same = api.post("/account/password", json={"current_password": "OldPassword1", "new_password": "OldPassword1"}, headers=world.headers["a"])
    assert same.status_code == 422

    ok = api.post("/account/password", json={"current_password": "OldPassword1", "new_password": "NewPassword2"}, headers=world.headers["a"])
    assert ok.status_code == 204

    world.db.refresh(user)
    assert verify_password("NewPassword2", user.password_hash)
    tokens = world.db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
    assert tokens and all(token.is_revoked for token in tokens)


# --- Notifications -------------------------------------------------------------


def test_notification_inbox(api, world):
    schedule(api, world)
    headers = world.headers["a"]

    inbox = api.get("/notifications", headers=headers).json()
    assert inbox["total"] == 1 and inbox["unread"] == 1
    note_id = inbox["items"][0]["id"]

    assert api.get("/notifications/unread-count", headers=headers).json() == {"unread": 1}

    # Another user cannot read or mark it.
    assert api.post(f"/notifications/{note_id}/read", headers=world.headers["b"]).status_code == 404

    marked = api.post(f"/notifications/{note_id}/read", headers=headers).json()
    assert marked["is_read"] is True and marked["read_at"] is not None
    assert api.get("/notifications?unread_only=true", headers=headers).json()["total"] == 0

    schedule(api, world, title="Second clinic", start_time=(datetime.now(timezone.utc) + timedelta(days=9)).isoformat(),
             end_time=(datetime.now(timezone.utc) + timedelta(days=9, hours=1)).isoformat())
    assert api.post("/notifications/read-all", headers=headers).json() == {"marked": 1}
