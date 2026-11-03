"""Self-registered students wait for a trainer before using the student portal."""

import uuid

from app.models import TrainerProfile
from tests.conftest import auth_headers, make_password
from tests.student_world import _user, api, tx_db, world  # noqa: F401


def _trainer(db, name="Assigned Trainer"):
    user = _user(db, "trainer", name)
    db.add(TrainerProfile(user_id=user.id, specialization="Endgames"))
    db.flush()
    return user


def _register_and_sign_in(api, email=None):
    email = email or f"signup-{uuid.uuid4().hex}@example.com"
    password = make_password()
    registered = api.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Self Signup"},
    )
    assert registered.status_code == 201

    tokens = api.post("/auth/login", json={"email": email, "password": password})
    assert tokens.status_code == 200
    headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}
    return registered.json(), headers


def test_access_requires_a_student(api, world):
    assert api.get("/student/access").status_code == 401
    assert api.get("/student/access", headers=world.trainer_headers).status_code == 403


def test_existing_student_is_ready_with_their_trainer(api, world):
    response = api.get("/student/access", headers=world.headers["a"])

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["trainer"]["full_name"] == "Test Trainer"


def test_new_signup_waits_then_gets_portal_once_trainer_assigned(api, tx_db):
    user, headers = _register_and_sign_in(api)

    # Signed in, but no profile yet: a waiting status instead of an error.
    waiting = api.get("/student/access", headers=headers)
    assert waiting.status_code == 200
    assert waiting.json() == {"status": "awaiting_trainer", "trainer": None}
    assert api.get("/student/dashboard", headers=headers).status_code == 404

    admin = _user(tx_db, "admin", "Academy Admin")
    trainer = _trainer(tx_db)
    assigned = api.patch(
        f"/admin/users/{user['id']}",
        json={"student_profile": {"trainer_user_id": str(trainer.id)}},
        headers=auth_headers(admin),
    )
    assert assigned.status_code == 200

    # The same session now reaches the portal; no new account is needed.
    ready = api.get("/student/access", headers=headers)
    assert ready.json()["status"] == "ready"
    assert ready.json()["trainer"]["full_name"] == "Assigned Trainer"
    assert api.get("/student/dashboard", headers=headers).status_code == 200


def test_admin_cannot_create_profile_without_a_trainer(api, tx_db):
    user, headers = _register_and_sign_in(api)
    admin = _user(tx_db, "admin", "Academy Admin")

    response = api.patch(
        f"/admin/users/{user['id']}",
        json={"student_profile": {"chess_rating": 900}},
        headers=auth_headers(admin),
    )

    assert response.status_code == 422
    assert api.get("/student/access", headers=headers).json()["status"] == (
        "awaiting_trainer"
    )
