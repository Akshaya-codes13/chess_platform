"""Admin module (M4) API tests.

Every test runs inside the rolled-back transaction from ``tdb``, and the
database may already hold seed data, so assertions compare deltas or filter
by a per-test marker instead of assuming empty tables.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.models import (
    Assignment,
    AssignmentRecipient,
    AuditLog,
    GroupMember,
    RefreshToken,
    StudentProfile,
    TrainerProfile,
    User,
)
from app.core.errors import ConflictError
from app.services import admin_service
from app.services.admin_service import AdminContext
from app.services.auth_service import create_refresh_token
from tests.trainer_fixtures import *  # noqa: F401,F403
from tests.trainer_fixtures import FORK, headers, now

PASSWORD = "Admin-pass-1"
SECRET_FIELDS = {"password", "password_hash", "token_hash", "refresh_token", "token_jti"}


@pytest.fixture()
def admin(factory):
    return factory.user("admin", "Root Admin")


@pytest.fixture()
def as_admin(api, admin):
    """Client helpers that send the admin's token."""

    class Client:
        def get(self, path, **kw):
            return api.get(path, headers=headers(admin), **kw)

        def post(self, path, json=None):
            return api.post(path, json=json, headers=headers(admin))

        def patch(self, path, json=None):
            return api.patch(path, json=json, headers=headers(admin))

        def put(self, path, json=None):
            return api.put(path, json=json, headers=headers(admin))

        def delete(self, path):
            return api.delete(path, headers=headers(admin))

    return Client()


@pytest.fixture()
def marker():
    return uuid.uuid4().hex[:10]


def assert_no_secrets(payload):
    if isinstance(payload, dict):
        assert not SECRET_FIELDS & payload.keys(), payload.keys()
        for value in payload.values():
            assert_no_secrets(value)
    elif isinstance(payload, list):
        for value in payload:
            assert_no_secrets(value)


def student_user(factory, trainer_profile, name="Student"):
    profile = factory.student(trainer_profile, name)
    return factory.db.get(User, profile.user_id), profile


# ----- Authorization -------------------------------------------------------

ADMIN_ENDPOINTS = [
    ("get", "/admin/dashboard"),
    ("get", "/admin/users"),
    ("get", "/admin/trainers"),
    ("get", "/admin/students"),
    ("get", "/admin/groups"),
    ("get", "/admin/puzzles"),
    ("get", "/admin/puzzles/filters"),
    ("get", "/admin/assignments"),
    ("get", "/admin/sessions"),
    ("get", "/admin/activity"),
    ("get", "/admin/reports/overview"),
]


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
def test_admin_routes_require_admin_role(api, factory, admin, method, path):
    call = getattr(api, method)
    trainer_user, trainer = factory.trainer()
    student, _ = student_user(factory, trainer)

    assert call(path).status_code == 401
    assert call(path, headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert call(path, headers=headers(student)).status_code == 403
    assert call(path, headers=headers(trainer_user)).status_code == 403
    assert call(path, headers=headers(admin)).status_code == 200


def test_mutations_are_admin_only(api, factory):
    trainer_user, trainer = factory.trainer()
    group = factory.group(trainer)
    body = {"email": "x@example.com", "password": PASSWORD, "full_name": "Someone"}

    for method, path, json in [
        ("post", "/admin/trainers", body),
        ("patch", f"/admin/users/{trainer_user.id}/status", {"is_active": False}),
        ("patch", f"/admin/users/{trainer_user.id}/role", {"role": "admin"}),
        ("patch", f"/admin/groups/{group.id}", {"name": "Hijacked"}),
    ]:
        response = getattr(api, method)(path, json=json, headers=headers(trainer_user))
        assert response.status_code == 403, path

    factory.db.refresh(trainer_user)
    assert trainer_user.role == "trainer" and trainer_user.is_active


def test_inactive_admin_is_rejected(api, factory, admin):
    admin.is_active = False
    factory.db.flush()
    assert api.get("/admin/dashboard", headers=headers(admin)).status_code == 401


# ----- Dashboard -----------------------------------------------------------


def test_dashboard_counts_come_from_the_database(as_admin, factory):
    before = as_admin.get("/admin/dashboard").json()

    trainer_user, trainer = factory.trainer()
    inactive, _ = student_user(factory, trainer)
    inactive.is_active = False
    student_user(factory, trainer)
    group = factory.group(trainer, name="Dashboard group")
    factory.session(trainer, group, now() + timedelta(days=2))
    factory.session(trainer, group, now() - timedelta(days=2), status="completed")
    factory.puzzle()
    factory.db.flush()

    after = as_admin.get("/admin/dashboard").json()
    assert after["users"]["total"] == before["users"]["total"] + 3
    assert after["users"]["trainers"] == before["users"]["trainers"] + 1
    assert after["users"]["students"] == before["users"]["students"] + 2
    assert after["users"]["inactive"] == before["users"]["inactive"] + 1
    assert after["groups"]["total"] == before["groups"]["total"] + 1
    assert after["sessions"]["upcoming"] == before["sessions"]["upcoming"] + 1
    assert after["sessions"]["completed"] == before["sessions"]["completed"] + 1
    assert after["puzzles"] == before["puzzles"] + 1
    assert after["assignments"]["total"] == sum(after["assignments"]["by_status"].values())
    assert_no_secrets(after)


def test_dashboard_recent_activity_lists_admin_actions(as_admin, factory):
    trainer_user, _ = factory.trainer()
    as_admin.patch(f"/admin/users/{trainer_user.id}/status", {"is_active": False})

    activity = as_admin.get("/admin/dashboard").json()["recent_activity"]
    assert activity[0]["action"] == "user.deactivated"
    assert activity[0]["entity_id"] == str(trainer_user.id)
    assert activity[0]["actor"]["full_name"] == "Root Admin"


# ----- Users: listing, details, creation -----------------------------------


def test_user_list_search_filters_and_pagination(as_admin, factory, marker):
    trainer_user, trainer = factory.trainer(f"Trainer {marker}")
    students = [student_user(factory, trainer, f"Pupil {marker} {i}")[0] for i in range(3)]
    students[0].is_active = False
    factory.db.flush()

    page = as_admin.get("/admin/users", params={"search": marker, "page_size": 2}).json()
    assert page["total"] == 4 and page["pages"] == 2 and len(page["items"]) == 2
    assert len(as_admin.get("/admin/users", params={"search": marker, "page": 2, "page_size": 2}).json()["items"]) == 2

    by_role = as_admin.get("/admin/users", params={"search": marker, "role": "student"}).json()
    assert by_role["total"] == 3

    inactive = as_admin.get("/admin/users", params={"search": marker, "is_active": "false"}).json()
    assert [u["id"] for u in inactive["items"]] == [str(students[0].id)]

    by_email = as_admin.get("/admin/users", params={"search": trainer_user.email.upper()}).json()
    assert by_email["total"] == 1

    assert_no_secrets(page)


def test_list_rejects_invalid_filters(as_admin):
    assert as_admin.get("/admin/users", params={"role": "superuser"}).status_code == 422
    assert as_admin.get("/admin/users", params={"page": 0}).status_code == 422
    assert as_admin.get("/admin/users", params={"page_size": 101}).status_code == 422


def test_search_treats_wildcards_literally(as_admin, factory, marker):
    factory.user("student", f"Percent {marker}")
    assert as_admin.get("/admin/users", params={"search": f"%{marker}"}).json()["total"] == 0


def test_user_detail_and_missing_records(as_admin, factory):
    trainer_user, trainer = factory.trainer()
    student, profile = student_user(factory, trainer)
    group = factory.group(trainer, [profile], name="Detail group")

    detail = as_admin.get(f"/admin/users/{student.id}").json()
    assert detail["student_profile"]["trainer"]["id"] == str(trainer_user.id)
    assert [g["id"] for g in detail["groups"]] == [str(group.id)]
    assert_no_secrets(detail)

    trainer_detail = as_admin.get(f"/admin/trainers/{trainer_user.id}").json()
    assert trainer_detail["trainer_stats"]["group_count"] == 1
    assert trainer_detail["trainer_stats"]["primary_student_count"] == 1
    assert trainer_detail["groups"][0]["id"] == str(group.id)

    assert as_admin.get(f"/admin/users/{uuid.uuid4()}").status_code == 404
    assert as_admin.get("/admin/users/not-a-uuid").status_code == 422
    # A student's ID is not a trainer's.
    assert as_admin.get(f"/admin/trainers/{student.id}").status_code == 404
    assert as_admin.get(f"/admin/students/{trainer_user.id}").status_code == 404


def test_student_detail_shows_assignments_and_progress(as_admin, factory):
    trainer_user, trainer = factory.trainer()
    student, profile = student_user(factory, trainer)
    assignment = Assignment(
        trainer_id=trainer.id, title="Forks", assignment_type="individual", status="published"
    )
    factory.db.add(assignment)
    factory.db.flush()
    factory.db.add(AssignmentRecipient(assignment_id=assignment.id, student_id=profile.id))
    factory.db.flush()

    detail = as_admin.get(f"/admin/students/{student.id}").json()
    assert detail["assignments"][0]["title"] == "Forks"
    assert detail["assignments"][0]["attempts"] == 0
    assert detail["assignments"][0]["trainer"]["id"] == str(trainer_user.id)


def test_create_trainer_account(as_admin, tdb, admin):
    response = as_admin.post(
        "/admin/trainers",
        {
            "email": "New.Trainer@Example.com",
            "password": PASSWORD,
            "full_name": "  New Trainer ",
            "profile": {"specialization": "Endgames", "experience_years": 4},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "trainer"
    assert body["email"] == "new.trainer@example.com"
    assert body["full_name"] == "New Trainer"
    assert body["trainer_profile"]["specialization"] == "Endgames"
    assert_no_secrets(body)

    user = tdb.get(User, uuid.UUID(body["id"]))
    assert user.password_hash != PASSWORD
    log = tdb.scalar(select(AuditLog).where(AuditLog.entity_id == user.id))
    assert log.action == "trainer.created" and log.actor_id == admin.id
    assert "password" not in str(log.details)


def test_create_student_account_requires_active_trainer(as_admin, factory):
    trainer_user, trainer = factory.trainer()
    body = {
        "email": f"s-{uuid.uuid4().hex}@example.com",
        "password": PASSWORD,
        "full_name": "New Student",
        "profile": {"trainer_user_id": str(trainer_user.id), "level": "intermediate"},
    }
    response = as_admin.post("/admin/students", body)
    assert response.status_code == 201, response.text
    assert response.json()["student_profile"]["level"] == "intermediate"
    assert response.json()["student_profile"]["trainer"]["id"] == str(trainer_user.id)

    missing_trainer = {**body, "email": f"s-{uuid.uuid4().hex}@example.com",
                       "profile": {"trainer_user_id": str(uuid.uuid4())}}
    assert as_admin.post("/admin/students", missing_trainer).status_code == 422

    no_trainer = {**body, "email": f"s-{uuid.uuid4().hex}@example.com", "profile": {}}
    assert as_admin.post("/admin/students", no_trainer).status_code == 422

    trainer_user.is_active = False
    factory.db.flush()
    inactive = {**body, "email": f"s-{uuid.uuid4().hex}@example.com"}
    assert as_admin.post("/admin/students", inactive).status_code == 422


def test_create_user_endpoint_and_validation(as_admin, factory):
    trainer_user, _ = factory.trainer()
    base = {"password": PASSWORD, "full_name": "Generic User"}

    trainer = as_admin.post("/admin/users", {**base, "email": f"t-{uuid.uuid4().hex}@example.com", "role": "trainer"})
    assert trainer.status_code == 201 and trainer.json()["trainer_profile"] is not None

    student = as_admin.post("/admin/users", {
        **base, "email": f"s-{uuid.uuid4().hex}@example.com", "role": "student",
        "student_profile": {"trainer_user_id": str(trainer_user.id)},
    })
    assert student.status_code == 201

    # Admins cannot be created directly, only promoted.
    assert as_admin.post("/admin/users", {**base, "email": "a@example.com", "role": "admin"}).status_code == 422
    # A student needs a profile with a trainer.
    assert as_admin.post("/admin/users", {**base, "email": "b@example.com", "role": "student"}).status_code == 422
    # Weak password, bad email, unknown field.
    assert as_admin.post("/admin/trainers", {**base, "email": "c@example.com", "password": "short"}).status_code == 422
    assert as_admin.post("/admin/trainers", {**base, "email": "not-an-email"}).status_code == 422
    assert as_admin.post("/admin/trainers", {**base, "email": "d@example.com", "is_active": False}).status_code == 422


def test_duplicate_email_is_rejected_case_insensitively(as_admin, factory):
    trainer_user, _ = factory.trainer()
    response = as_admin.post("/admin/trainers", {
        "email": trainer_user.email.upper(), "password": PASSWORD, "full_name": "Copy",
    })
    assert response.status_code == 409


# ----- Users: updates, roles, status ---------------------------------------


def test_update_user_profile(as_admin, factory, tdb):
    trainer_user, trainer = factory.trainer()
    other_trainer_user, other_trainer = factory.trainer()
    student, profile = student_user(factory, trainer)
    student.is_verified = True
    tdb.flush()

    new_email = f"renamed-{uuid.uuid4().hex}@example.com"
    response = as_admin.patch(f"/admin/users/{student.id}", {
        "full_name": "Renamed Student",
        "email": new_email.upper(),
        "phone": "+1 555 0100",
        "student_profile": {"chess_rating": 1350, "trainer_user_id": str(other_trainer_user.id)},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "Renamed Student"
    assert body["email"] == new_email
    # The new address has not been verified yet.
    assert body["is_verified"] is False
    assert body["student_profile"]["chess_rating"] == 1350
    assert body["student_profile"]["trainer"]["id"] == str(other_trainer_user.id)

    trainer_update = as_admin.patch(f"/admin/users/{trainer_user.id}", {
        "trainer_profile": {"bio": "Coach", "experience_years": 9},
    })
    assert trainer_update.json()["trainer_profile"]["experience_years"] == 9


def test_update_user_rejects_bad_input(as_admin, factory):
    trainer_user, trainer = factory.trainer()
    student, _ = student_user(factory, trainer)

    # Role and secrets cannot be changed through the profile endpoint.
    for body in ({"role": "admin"}, {"password_hash": "x"}, {"is_active": False}):
        assert as_admin.patch(f"/admin/users/{student.id}", body).status_code == 422
    assert as_admin.patch(f"/admin/users/{student.id}", {"full_name": None}).status_code == 422
    assert as_admin.patch(f"/admin/users/{student.id}", {"full_name": " "}).status_code == 422
    # Profile type must match the role.
    assert as_admin.patch(f"/admin/users/{student.id}", {"trainer_profile": {"bio": "x"}}).status_code == 422
    assert as_admin.patch(f"/admin/users/{student.id}", {
        "student_profile": {"date_of_birth": "2999-01-01"},
    }).status_code == 422
    # Email already used by someone else.
    assert as_admin.patch(f"/admin/users/{student.id}", {"email": trainer_user.email}).status_code == 409
    assert as_admin.patch(f"/admin/users/{uuid.uuid4()}", {"full_name": "Ghost"}).status_code == 404


def test_self_registered_student_gets_profile_on_update(as_admin, factory):
    trainer_user, _ = factory.trainer()
    student = factory.user("student", "Self Registered")

    listed = as_admin.get("/admin/students", params={"search": student.email}).json()["items"][0]
    assert listed["level"] is None and listed["trainer"] is None

    missing = as_admin.patch(f"/admin/users/{student.id}", {"student_profile": {"level": "advanced"}})
    assert missing.status_code == 422

    created = as_admin.patch(f"/admin/users/{student.id}", {
        "student_profile": {"level": "advanced", "trainer_user_id": str(trainer_user.id)},
    })
    assert created.status_code == 200
    assert created.json()["student_profile"]["level"] == "advanced"


def test_role_changes_keep_data_consistent(as_admin, factory, tdb):
    trainer_user, trainer = factory.trainer()
    student, profile = student_user(factory, trainer)
    group = factory.group(trainer, [profile])

    # A student in a group must leave it first.
    assert as_admin.patch(f"/admin/users/{student.id}/role", {"role": "trainer"}).status_code == 409
    # A trainer with groups and students must hand them over first.
    assert as_admin.patch(f"/admin/users/{trainer_user.id}/role", {"role": "student"}).status_code == 409

    tdb.delete(tdb.scalar(select(GroupMember).where(GroupMember.group_id == group.id)))
    tdb.flush()

    promoted = as_admin.patch(f"/admin/users/{student.id}/role", {"role": "trainer"})
    assert promoted.status_code == 200 and promoted.json()["role"] == "trainer"
    assert tdb.scalar(select(TrainerProfile).where(TrainerProfile.user_id == student.id))

    # Becoming a student without a profile needs a trainer.
    plain = factory.user("admin", "Second Admin")
    assert as_admin.patch(f"/admin/users/{plain.id}/role", {"role": "student"}).status_code == 422
    demoted = as_admin.patch(f"/admin/users/{plain.id}/role", {
        "role": "student", "trainer_user_id": str(trainer_user.id),
    })
    assert demoted.status_code == 200
    assert tdb.scalar(select(StudentProfile).where(StudentProfile.user_id == plain.id))

    assert as_admin.patch(f"/admin/users/{trainer_user.id}/role", {"role": "owner"}).status_code == 422


def test_promote_to_admin_is_explicit_and_audited(as_admin, factory, tdb):
    trainer_user, _ = factory.trainer()
    response = as_admin.patch(f"/admin/users/{trainer_user.id}/role", {"role": "admin"})
    assert response.status_code == 200 and response.json()["role"] == "admin"

    log = tdb.scalar(select(AuditLog).where(
        AuditLog.entity_id == trainer_user.id, AuditLog.action == "user.role_changed"
    ))
    assert log.details == {"from": "trainer", "to": "admin"}


def test_admin_cannot_change_own_role_or_status(as_admin, admin):
    assert as_admin.patch(f"/admin/users/{admin.id}/role", {"role": "trainer"}).status_code == 409
    assert as_admin.patch(f"/admin/users/{admin.id}/status", {"is_active": False}).status_code == 409


def test_deactivation_revokes_sessions_and_blocks_access(api, as_admin, factory, tdb):
    trainer_user, _ = factory.trainer()
    create_refresh_token(tdb, trainer_user.id)

    response = as_admin.patch(f"/admin/users/{trainer_user.id}/status", {"is_active": False})
    assert response.status_code == 200 and response.json()["is_active"] is False

    tokens = tdb.scalars(select(RefreshToken).where(RefreshToken.user_id == trainer_user.id)).all()
    assert tokens and all(token.is_revoked for token in tokens)
    assert api.get("/auth/me", headers=headers(trainer_user)).status_code == 401

    reactivated = as_admin.patch(f"/admin/users/{trainer_user.id}/status", {"is_active": True})
    assert reactivated.json()["is_active"] is True
    assert as_admin.patch(f"/admin/users/{trainer_user.id}/status", {}).status_code == 422


def test_other_admins_can_be_deactivated(as_admin, factory):
    other = factory.user("admin", "Other Admin")
    assert as_admin.patch(f"/admin/users/{other.id}/status", {"is_active": False}).status_code == 200


def test_last_active_admin_is_protected(tdb, factory, admin):
    # Leave ``admin`` as the only active admin inside this transaction.
    tdb.execute(
        update(User)
        .where(User.role == "admin", User.id != admin.id)
        .values(is_active=False)
    )
    tdb.flush()
    # The API blocks self-changes first, so exercise the guard directly with
    # an actor other than the target (e.g. a concurrent request).
    ctx = AdminContext(actor=factory.user("admin", "Racing Admin"))
    ctx.actor.is_active = False
    tdb.flush()

    with pytest.raises(ConflictError):
        admin_service.change_status(tdb, ctx, admin.id, False)
    with pytest.raises(ConflictError):
        admin_service.change_role(tdb, ctx, admin.id, "trainer")

    tdb.refresh(admin)
    assert admin.is_active and admin.role == "admin"


# ----- Trainers and students lists -----------------------------------------


def test_trainer_and_student_lists(as_admin, factory, marker):
    trainer_user, trainer = factory.trainer(f"Coach {marker}")
    _, profile_a = student_user(factory, trainer, f"Kid {marker} A")
    student_b, _ = student_user(factory, trainer, f"Kid {marker} B")
    group = factory.group(trainer, [profile_a])

    trainers = as_admin.get("/admin/trainers", params={"search": marker}).json()
    assert trainers["total"] == 1
    assert trainers["items"][0]["group_count"] == 1
    assert trainers["items"][0]["primary_student_count"] == 2

    students = as_admin.get("/admin/students", params={"search": marker}).json()
    assert students["total"] == 2
    assert {s["trainer"]["id"] for s in students["items"]} == {str(trainer_user.id)}

    in_group = as_admin.get("/admin/students", params={"search": marker, "group_id": str(group.id)}).json()
    assert [s["full_name"] for s in in_group["items"]] == [f"Kid {marker} A"]

    outside = as_admin.get("/admin/students", params={"search": marker, "exclude_group_id": str(group.id)}).json()
    assert [s["id"] for s in outside["items"]] == [str(student_b.id)]

    by_trainer = as_admin.get("/admin/students", params={"trainer_id": str(trainer_user.id)}).json()
    assert by_trainer["total"] == 2


# ----- Groups --------------------------------------------------------------


def test_create_and_edit_group(as_admin, factory, marker):
    trainer_user, trainer = factory.trainer()
    student, _ = student_user(factory, trainer)

    response = as_admin.post("/admin/groups", {
        "name": f"  Juniors {marker} ",
        "description": "Saturday class",
        "trainer_user_id": str(trainer_user.id),
        "student_user_ids": [str(student.id)],
    })
    assert response.status_code == 201, response.text
    group = response.json()
    assert group["name"] == f"Juniors {marker}"
    assert group["trainer"]["id"] == str(trainer_user.id)
    assert group["member_count"] == 1 and group["members"][0]["id"] == str(student.id)

    duplicate = as_admin.post("/admin/groups", {
        "name": f"juniors {marker}", "trainer_user_id": str(trainer_user.id),
    })
    assert duplicate.status_code == 409

    edited = as_admin.patch(f"/admin/groups/{group['id']}", {"name": f"Seniors {marker}", "is_active": False})
    assert edited.status_code == 200
    assert edited.json()["name"] == f"Seniors {marker}" and edited.json()["is_active"] is False

    listed = as_admin.get("/admin/groups", params={"search": marker, "is_active": "false"}).json()
    assert [g["id"] for g in listed["items"]] == [group["id"]]
    assert listed["items"][0]["member_count"] == 1

    by_trainer = as_admin.get("/admin/groups", params={"trainer_id": str(trainer_user.id)}).json()
    assert by_trainer["total"] == 1


def test_group_validation_and_missing_records(as_admin, factory):
    trainer_user, trainer = factory.trainer()
    group = factory.group(trainer)

    assert as_admin.post("/admin/groups", {"name": "X"}).status_code == 422
    assert as_admin.post("/admin/groups", {"name": "Valid", "trainer_user_id": str(uuid.uuid4())}).status_code == 422
    student_as_trainer = factory.user("student")
    assert as_admin.post("/admin/groups", {"name": "Valid", "trainer_user_id": str(student_as_trainer.id)}).status_code == 422
    assert as_admin.patch(f"/admin/groups/{group.id}", {"name": None}).status_code == 422
    assert as_admin.patch(f"/admin/groups/{group.id}", {"trainer_id": str(uuid.uuid4())}).status_code == 422
    assert as_admin.get(f"/admin/groups/{uuid.uuid4()}").status_code == 404
    assert as_admin.patch(f"/admin/groups/{uuid.uuid4()}", {"name": "Ghost"}).status_code == 404


def test_group_membership(as_admin, factory):
    trainer_user, trainer = factory.trainer()
    group = factory.group(trainer)
    student_a, _ = student_user(factory, trainer, "Alpha")
    student_b, _ = student_user(factory, trainer, "Bravo")
    path = f"/admin/groups/{group.id}/students"

    added = as_admin.post(path, {"student_user_ids": [str(student_a.id), str(student_b.id)]})
    assert added.status_code == 200
    assert {m["id"] for m in added.json()["members"]} == {str(student_a.id), str(student_b.id)}

    # Duplicate memberships are refused and nothing changes.
    duplicate = as_admin.post(path, {"student_user_ids": [str(student_a.id)]})
    assert duplicate.status_code == 409 and "Alpha" in duplicate.json()["detail"]

    removed = as_admin.delete(f"{path}/{student_a.id}")
    assert removed.status_code == 204
    assert as_admin.delete(f"{path}/{student_a.id}").status_code == 404
    assert [m["id"] for m in as_admin.get(f"/admin/groups/{group.id}").json()["members"]] == [str(student_b.id)]


def test_group_membership_rejects_invalid_students(as_admin, factory, tdb):
    trainer_user, trainer = factory.trainer()
    group = factory.group(trainer)
    student, _ = student_user(factory, trainer)
    no_profile = factory.user("student", "No Profile")
    path = f"/admin/groups/{group.id}/students"

    assert as_admin.post(path, {"student_user_ids": [str(uuid.uuid4())]}).status_code == 422
    assert as_admin.post(path, {"student_user_ids": [str(trainer_user.id)]}).status_code == 422
    assert as_admin.post(path, {"student_user_ids": [str(no_profile.id)]}).status_code == 422
    assert as_admin.post(path, {"student_user_ids": [str(student.id)] * 2}).status_code == 422
    assert as_admin.post(path, {"student_user_ids": []}).status_code == 422
    # A batch with one bad ID adds nobody.
    assert as_admin.post(path, {"student_user_ids": [str(student.id), str(uuid.uuid4())]}).status_code == 422
    assert tdb.scalar(select(GroupMember).where(GroupMember.group_id == group.id)) is None

    assert as_admin.post(f"/admin/groups/{uuid.uuid4()}/students", {"student_user_ids": [str(student.id)]}).status_code == 404
    assert as_admin.delete(f"/admin/groups/{uuid.uuid4()}/students/{student.id}").status_code == 404


def test_assign_group_trainer(as_admin, factory):
    first_user, first = factory.trainer()
    second_user, _ = factory.trainer()
    group = factory.group(first)
    path = f"/admin/groups/{group.id}/trainer"

    response = as_admin.put(path, {"trainer_user_id": str(second_user.id)})
    assert response.status_code == 200
    assert response.json()["trainer"]["id"] == str(second_user.id)

    second_user.is_active = False
    factory.db.flush()
    assert as_admin.put(path, {"trainer_user_id": str(first_user.id)}).status_code == 200
    assert as_admin.put(path, {"trainer_user_id": str(second_user.id)}).status_code == 422
    assert as_admin.put(path, {"trainer_user_id": str(uuid.uuid4())}).status_code == 422
    assert as_admin.put(f"/admin/groups/{uuid.uuid4()}/trainer", {"trainer_user_id": str(first_user.id)}).status_code == 404


# ----- Puzzles -------------------------------------------------------------


def test_puzzle_overview_flags_broken_records(as_admin, factory):
    good = factory.puzzle(FORK)
    broken = factory.puzzle(("7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "a1a8"))

    listed = as_admin.get("/admin/puzzles", params={"source": "test", "page_size": 100}).json()
    by_id = {p["id"]: p for p in listed["items"]}
    assert any(issue.startswith("Illegal move") for issue in by_id[str(broken.id)]["issues"])
    assert "No category." in by_id[str(good.id)]["issues"]
    assert not any("move" in issue.lower() for issue in by_id[str(good.id)]["issues"])

    incomplete = as_admin.get("/admin/puzzles", params={"incomplete_only": "true", "source": "test", "page_size": 100}).json()
    assert str(broken.id) in {p["id"] for p in incomplete["items"]}

    detail = as_admin.get(f"/admin/puzzles/{good.id}").json()
    assert detail["solution"] == FORK[1]
    assert detail["usage"] == {"assignment_count": 0, "attempt_count": 0, "solved_count": 0}
    assert as_admin.get(f"/admin/puzzles/{uuid.uuid4()}").status_code == 404

    filters = as_admin.get("/admin/puzzles/filters").json()
    assert "test" in filters["sources"] and "published" in filters["statuses"]


def test_puzzle_archive_and_publish(as_admin, factory):
    puzzle = factory.puzzle(FORK)
    broken = factory.puzzle(("7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "a1a8"), status="draft")

    archived = as_admin.post(f"/admin/puzzles/{puzzle.id}/archive")
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    assert as_admin.post(f"/admin/puzzles/{puzzle.id}/archive").status_code == 409

    listed = as_admin.get("/admin/puzzles", params={"status": "archived", "source": "test", "page_size": 100}).json()
    assert str(puzzle.id) in {p["id"] for p in listed["items"]}

    assert as_admin.post(f"/admin/puzzles/{puzzle.id}/publish").json()["status"] == "published"
    # A malformed puzzle cannot be published.
    assert as_admin.post(f"/admin/puzzles/{broken.id}/publish").status_code == 422
    assert as_admin.post(f"/admin/puzzles/{puzzle.id}/delete").status_code == 422


# ----- Oversight -----------------------------------------------------------


def test_assignment_session_and_report_overviews(as_admin, factory, marker):
    trainer_user, trainer = factory.trainer()
    student, profile = student_user(factory, trainer)
    group = factory.group(trainer, [profile])
    assignment = Assignment(
        trainer_id=trainer.id, group_id=group.id, title=f"Mates {marker}",
        assignment_type="group", status="published",
    )
    factory.db.add(assignment)
    factory.db.flush()
    factory.db.add(AssignmentRecipient(assignment_id=assignment.id, student_id=profile.id))
    session = factory.session(trainer, group, now() + timedelta(days=1))
    factory.db.flush()

    assignments = as_admin.get("/admin/assignments", params={"search": marker}).json()
    assert assignments["total"] == 1
    item = assignments["items"][0]
    assert item["recipient_count"] == 1 and item["group"]["id"] == str(group.id)
    assert item["trainer"]["id"] == str(trainer_user.id)
    assert as_admin.get("/admin/assignments", params={"status": "bogus"}).status_code == 422

    sessions = as_admin.get("/admin/sessions", params={"timeframe": "upcoming", "group_id": str(group.id)}).json()
    assert [s["id"] for s in sessions["items"]] == [str(session.id)]
    assert as_admin.get("/admin/sessions", params={"timeframe": "past", "group_id": str(group.id)}).json()["total"] == 0

    report = as_admin.get("/admin/reports/overview").json()
    assert report["assignments_by_status"]["published"] >= 1
    assert set(report["games"]) == {"total", "by_status", "by_type", "by_result"}
    assert 0 <= report["puzzle_attempts"]["solve_rate"] <= 100


def test_activity_log_is_paginated_and_filterable(as_admin, factory):
    trainer_user, trainer = factory.trainer()
    group = factory.group(trainer)
    as_admin.patch(f"/admin/groups/{group.id}", {"description": "Updated"})

    page = as_admin.get("/admin/activity", params={"entity_type": "group", "action": "group.updated"}).json()
    assert page["items"][0]["entity_id"] == str(group.id)
    assert page["items"][0]["details"] == {"fields": ["description"]}
