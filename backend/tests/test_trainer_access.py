"""Trainer route authorization, group ownership and profile rules."""

import pytest

from tests.trainer_fixtures import *  # noqa: F401,F403
from tests.trainer_fixtures import headers

TRAINER_GET_ROUTES = [
    "/trainer/dashboard",
    "/trainer/profile",
    "/trainer/groups",
    "/trainer/puzzles",
    "/trainer/assignments",
    "/trainer/sessions",
]


@pytest.mark.parametrize("path", TRAINER_GET_ROUTES)
def test_students_and_admins_are_forbidden(api, factory, path):
    for role in ("student", "admin"):
        user = factory.user(role)
        assert api.get(path, headers=headers(user)).status_code == 403, (path, role)


@pytest.mark.parametrize("path", TRAINER_GET_ROUTES)
def test_unauthenticated_requests_get_401(api, path):
    assert api.get(path).status_code == 401


def test_trainer_without_profile_is_forbidden(api, factory):
    user = factory.user("trainer")
    response = api.get("/trainer/dashboard", headers=headers(user))
    assert response.status_code == 403
    assert "trainer profile" in response.json()["detail"]


def test_trainer_sees_only_own_groups(api, factory):
    user_a, trainer_a = factory.trainer()
    _, trainer_b = factory.trainer()
    own = factory.group(trainer_a, [factory.student(trainer_a)], name="Mine")
    factory.group(trainer_b, name="Theirs")

    body = api.get("/trainer/groups", headers=headers(user_a)).json()

    assert [group["id"] for group in body["items"]] == [str(own.id)]
    assert body["items"][0]["student_count"] == 1
    assert body["total"] == 1


def test_trainer_cannot_open_another_trainers_group(api, factory):
    user_a, _ = factory.trainer()
    _, trainer_b = factory.trainer()
    student = factory.student(trainer_b)
    other = factory.group(trainer_b, [student])

    for path in (
        f"/trainer/groups/{other.id}",
        f"/trainer/groups/{other.id}/students",
        f"/trainer/groups/{other.id}/performance",
        f"/trainer/groups/{other.id}/assignments",
        f"/trainer/students/{student.id}/performance",
    ):
        assert api.get(path, headers=headers(user_a)).status_code == 404, path


def test_group_detail_and_students(api, factory):
    user, trainer = factory.trainer()
    alice = factory.student(trainer, "Alice")
    bob = factory.student(trainer, "Bob")
    group = factory.group(trainer, [alice, bob])

    detail = api.get(f"/trainer/groups/{group.id}", headers=headers(user)).json()
    assert detail["student_count"] == 2
    assert detail["upcoming_session_count"] == 0

    students = api.get(
        f"/trainer/groups/{group.id}/students",
        params={"search": "ali", "page_size": 5},
        headers=headers(user),
    ).json()
    assert [s["full_name"] for s in students["items"]] == ["Alice"]
    assert "password_hash" not in students["items"][0]


def test_list_endpoints_are_paginated(api, factory):
    user, trainer = factory.trainer()
    for index in range(3):
        factory.group(trainer, name=f"Group {index}")

    body = api.get("/trainer/groups", params={"page": 2, "page_size": 2}, headers=headers(user)).json()

    assert body["total"] == 3
    assert body["pages"] == 2
    assert [group["name"] for group in body["items"]] == ["Group 2"]


def test_profile_update_allows_permitted_fields(api, factory):
    user, _ = factory.trainer()

    response = api.patch(
        "/trainer/profile",
        json={"full_name": "Coach Kasparova", "bio": "IM", "experience_years": 9},
        headers=headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Coach Kasparova"
    assert body["experience_years"] == 9
    assert "password_hash" not in body


@pytest.mark.parametrize("field, value", [("role", "admin"), ("is_active", False), ("email", "x@example.com")])
def test_profile_cannot_change_admin_managed_fields(api, factory, tdb, field, value):
    user, _ = factory.trainer()

    response = api.patch("/trainer/profile", json={field: value}, headers=headers(user))

    assert response.status_code == 422
    tdb.refresh(user)
    assert user.role == "trainer"
    assert user.is_active is True
