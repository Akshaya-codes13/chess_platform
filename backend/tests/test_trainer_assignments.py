"""Trainer assignment creation, validation, lifecycle and progress."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import AssignmentRecipient, GroupMember, Submission
from tests.trainer_fixtures import *  # noqa: F401,F403
from tests.trainer_fixtures import FORK, headers, now


@pytest.fixture()
def setup(factory):
    user, trainer = factory.trainer()
    students = [factory.student(trainer, name) for name in ("Ann", "Ben", "Cal")]
    group = factory.group(trainer, students)
    puzzles = [factory.puzzle(), factory.puzzle(FORK)]
    return user, trainer, group, students, puzzles


def payload(group, puzzles, **overrides):
    return {
        "title": "Tactics week 1",
        "group_id": str(group.id),
        "puzzle_ids": [str(p.id) for p in puzzles],
        "due_date": (now() + timedelta(days=7)).isoformat(),
        **overrides,
    }


def test_create_and_publish_group_assignment(api, setup):
    user, _, group, students, puzzles = setup

    response = api.post("/trainer/assignments", json=payload(group, puzzles, publish=True), headers=headers(user))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "published"
    assert body["assignment_type"] == "group"
    assert body["puzzle_count"] == 2
    assert body["recipient_count"] == 3
    assert [p["display_order"] for p in body["puzzles"]] == [1, 2]
    assert body["published_at"] is not None


def test_create_for_selected_students(api, setup):
    user, _, group, students, puzzles = setup

    body = api.post(
        "/trainer/assignments",
        json=payload(group, puzzles, student_ids=[str(students[0].id)]),
        headers=headers(user),
    ).json()

    assert body["assignment_type"] == "individual"
    assert [r["student_id"] for r in body["recipients"]] == [str(students[0].id)]


def test_reject_group_of_another_trainer(api, factory, setup):
    user, _, _, _, puzzles = setup
    _, other = factory.trainer()
    foreign = factory.group(other, [factory.student(other)])

    response = api.post("/trainer/assignments", json=payload(foreign, puzzles), headers=headers(user))

    assert response.status_code == 404


def test_reject_inactive_group(api, factory, setup):
    user, trainer, _, _, puzzles = setup
    inactive = factory.group(trainer, [factory.student(trainer)], is_active=False)

    assert api.post("/trainer/assignments", json=payload(inactive, puzzles), headers=headers(user)).status_code == 409


def test_reject_students_outside_group(api, factory, setup):
    user, trainer, group, _, puzzles = setup
    outsider = factory.student(trainer, "Outsider")

    response = api.post(
        "/trainer/assignments",
        json=payload(group, puzzles, student_ids=[str(outsider.id)]),
        headers=headers(user),
    )

    assert response.status_code == 422
    assert "members" in response.json()["detail"]


def test_reject_publishing_empty_assignment(api, setup):
    user, _, group, _, _ = setup

    immediate = api.post("/trainer/assignments", json=payload(group, [], publish=True), headers=headers(user))
    draft = api.post("/trainer/assignments", json=payload(group, []), headers=headers(user))
    later = api.post(f"/trainer/assignments/{draft.json()['id']}/publish", headers=headers(user))

    assert immediate.status_code == 422
    assert draft.status_code == 201
    assert later.status_code == 422
    assert "at least one puzzle" in later.json()["detail"]


def test_reject_unpublished_or_unknown_puzzles(api, factory, setup):
    import uuid

    user, trainer, group, _, _ = setup
    draft_puzzle = factory.puzzle(owner=trainer, status="draft")

    for puzzle_ids in ([str(draft_puzzle.id)], [str(uuid.uuid4())]):
        response = api.post(
            "/trainer/assignments", json={**payload(group, []), "puzzle_ids": puzzle_ids}, headers=headers(user)
        )
        assert response.status_code == 422


def test_validate_dates(api, setup):
    user, _, group, _, puzzles = setup
    start = now() + timedelta(days=5)

    inverted = api.post(
        "/trainer/assignments",
        json=payload(group, puzzles, start_date=start.isoformat(), due_date=(start - timedelta(days=1)).isoformat()),
        headers=headers(user),
    )
    past_due = api.post(
        "/trainer/assignments",
        json=payload(group, puzzles, due_date=(now() - timedelta(days=1)).isoformat(), publish=True),
        headers=headers(user),
    )
    naive = api.post(
        "/trainer/assignments", json=payload(group, puzzles, due_date="2030-01-01T10:00:00"), headers=headers(user)
    )

    assert inverted.status_code == 422
    assert past_due.status_code == 422
    assert naive.status_code == 422


def test_prevent_duplicate_recipients(api, tdb, factory, setup):
    user, trainer, group, students, puzzles = setup

    duplicate = api.post(
        "/trainer/assignments",
        json=payload(group, puzzles, student_ids=[str(students[0].id)] * 2),
        headers=headers(user),
    )
    assert duplicate.status_code == 422

    created = api.post("/trainer/assignments", json=payload(group, puzzles), headers=headers(user)).json()
    # A student joins before publishing; publishing re-syncs without duplicates.
    late_joiner = factory.student(trainer, "Late")
    tdb.add(GroupMember(group_id=group.id, student_id=late_joiner.id))
    tdb.flush()
    api.post(f"/trainer/assignments/{created['id']}/publish", headers=headers(user))

    rows = tdb.scalar(
        select(func.count()).select_from(AssignmentRecipient).where(AssignmentRecipient.assignment_id == created["id"])
    )
    distinct = tdb.scalar(
        select(func.count(AssignmentRecipient.student_id.distinct())).where(
            AssignmentRecipient.assignment_id == created["id"]
        )
    )
    assert rows == distinct == 4


def test_only_drafts_are_editable(api, setup):
    user, _, group, _, puzzles = setup
    draft = api.post("/trainer/assignments", json=payload(group, puzzles), headers=headers(user)).json()

    renamed = api.patch(f"/trainer/assignments/{draft['id']}", json={"title": "Renamed"}, headers=headers(user))
    api.post(f"/trainer/assignments/{draft['id']}/publish", headers=headers(user))
    locked = api.patch(f"/trainer/assignments/{draft['id']}", json={"title": "Again"}, headers=headers(user))
    closed = api.post(f"/trainer/assignments/{draft['id']}/close", headers=headers(user))

    assert renamed.json()["title"] == "Renamed"
    assert locked.status_code == 409
    assert closed.json()["status"] == "completed"


def test_other_trainer_cannot_see_or_edit_assignment(api, factory, setup):
    user, _, group, _, puzzles = setup
    created = api.post("/trainer/assignments", json=payload(group, puzzles), headers=headers(user)).json()
    other_user, _ = factory.trainer()

    assert api.get(f"/trainer/assignments/{created['id']}", headers=headers(other_user)).status_code == 404
    assert api.patch(
        f"/trainer/assignments/{created['id']}", json={"title": "Hijack"}, headers=headers(other_user)
    ).status_code == 404
    assert api.get("/trainer/assignments", headers=headers(other_user)).json()["total"] == 0


def test_progress_calculation(api, tdb, factory, setup):
    user, _, group, (ann, ben, cal), puzzles = setup
    created = api.post("/trainer/assignments", json=payload(group, puzzles, publish=True), headers=headers(user)).json()
    assignment_id = created["id"]

    # Ann solves both (after one failure), Ben solves one, Cal does nothing.
    factory.attempt(ann, puzzles[0], False, assignment_id)
    factory.attempt(ann, puzzles[0], True, assignment_id)
    factory.attempt(ann, puzzles[1], True, assignment_id)
    factory.attempt(ben, puzzles[0], True, assignment_id)
    # Attempts outside the assignment do not count towards it.
    factory.attempt(ben, puzzles[1], True, None)
    tdb.add(Submission(assignment_id=assignment_id, student_id=ann.id, attempt_number=1, score=2, status="graded"))
    tdb.flush()

    progress = api.get(f"/trainer/assignments/{assignment_id}/progress", headers=headers(user)).json()
    by_name = {r["full_name"]: r for r in progress["recipients"]}

    assert progress["puzzles_total"] == 2
    assert progress["recipients_total"] == 3
    assert (progress["completed_count"], progress["in_progress_count"], progress["not_started_count"]) == (1, 1, 1)
    assert progress["completion_rate"] == 33.3
    assert progress["average_completion_percent"] == 50.0
    assert by_name["Ann"]["status"] == "completed" and by_name["Ann"]["attempts"] == 3
    assert by_name["Ann"]["submission_status"] == "graded"
    assert by_name["Ben"]["completion_percent"] == 50.0
    assert by_name["Cal"]["status"] == "not_started"

    summary = api.get(f"/trainer/assignments/{assignment_id}", headers=headers(user)).json()
    assert summary["completed_count"] == 1
