"""Student performance metrics and dashboard data isolation."""

from datetime import timedelta

from app.models import Assignment, AssignmentPuzzle, AssignmentRecipient, SessionAttendance
from tests.trainer_fixtures import *  # noqa: F401,F403
from tests.trainer_fixtures import FORK, headers, now


def make_assignment(db, trainer, group, puzzles, students, status="published"):
    assignment = Assignment(
        trainer_id=trainer.id, group_id=group.id, title="Set", assignment_type="group", status=status,
    )
    db.add(assignment)
    db.flush()
    for order, puzzle in enumerate(puzzles, start=1):
        db.add(AssignmentPuzzle(assignment_id=assignment.id, puzzle_id=puzzle.id, display_order=order))
    for student in students:
        db.add(AssignmentRecipient(assignment_id=assignment.id, student_id=student.id))
    db.flush()
    return assignment


def test_student_accuracy_and_completion(api, tdb, factory):
    user, trainer = factory.trainer()
    ann = factory.student(trainer, "Ann")
    group = factory.group(trainer, [ann])
    p1, p2 = factory.puzzle(), factory.puzzle(FORK)

    done = make_assignment(tdb, trainer, group, [p1], [ann])
    pending = make_assignment(tdb, trainer, group, [p1, p2], [ann])
    make_assignment(tdb, trainer, group, [p2], [ann], status="draft")  # not counted

    # 4 attempts, 3 solved; distinct puzzles: 2 attempted, 2 solved.
    factory.attempt(ann, p1, False, done.id)
    factory.attempt(ann, p1, True, done.id)
    factory.attempt(ann, p1, True, pending.id)
    factory.attempt(ann, p2, True, None)

    present = factory.session(trainer, group, now() - timedelta(days=3))
    absent = factory.session(trainer, group, now() - timedelta(days=2))
    excused = factory.session(trainer, group, now() - timedelta(days=1))
    for session, status in ((present, "present"), (absent, "absent"), (excused, "excused")):
        tdb.add(SessionAttendance(session_id=session.id, student_id=ann.id, status=status))
    tdb.flush()

    body = api.get(f"/trainer/students/{ann.id}/performance", headers=headers(user)).json()
    m = body["metrics"]

    assert (m["total_attempts"], m["solved_attempts"]) == (4, 3)
    assert m["accuracy_percent"] == 75.0
    assert (m["puzzles_attempted"], m["puzzles_solved"]) == (2, 2)
    assert (m["assignments_received"], m["assignments_completed"]) == (2, 1)
    assert m["assignment_completion_rate"] == 50.0
    # Excused is left out: 1 attended of 2 counted sessions.
    assert (m["sessions_recorded"], m["sessions_attended"], m["attendance_rate"]) == (2, 1, 50.0)
    assert body["groups"] == [{"id": str(group.id), "name": group.name}]
    assert len(body["progress"]) == 12 and body["progress"][-1]["attempts"] == 4
    assert {a["completed"] for a in body["assignments"]} == {True, False}


def test_no_data_is_reported_as_none_not_zero(api, factory):
    user, trainer = factory.trainer()
    ann = factory.student(trainer)
    factory.group(trainer, [ann])

    m = api.get(f"/trainer/students/{ann.id}/performance", headers=headers(user)).json()["metrics"]

    assert m["accuracy_percent"] is None
    assert m["assignment_completion_rate"] is None
    assert m["attendance_rate"] is None


def test_group_performance_aggregates(api, factory):
    user, trainer = factory.trainer()
    ann, ben = factory.student(trainer, "Ann"), factory.student(trainer, "Ben")
    group = factory.group(trainer, [ann, ben])
    puzzle = factory.puzzle()
    factory.attempt(ann, puzzle, True)
    factory.attempt(ann, puzzle, True)
    factory.attempt(ann, puzzle, True)
    factory.attempt(ben, puzzle, False)

    body = api.get(f"/trainer/groups/{group.id}/performance", headers=headers(user)).json()

    # Pooled, not averaged: 3 of 4 attempts, although per-student rates are 100% and 0%.
    assert body["metrics"]["accuracy_percent"] == 75.0
    assert body["metrics"]["active_students"] == 2
    assert [s["metrics"]["accuracy_percent"] for s in body["students"]] == [100.0, 0.0]


def test_metrics_isolated_between_trainers(api, tdb, factory):
    """A student shared by two trainers' groups only shows each trainer's
    own assignments and sessions."""
    user_a, trainer_a = factory.trainer()
    user_b, trainer_b = factory.trainer()
    shared = factory.student(trainer_a, "Shared")
    group_a = factory.group(trainer_a, [shared])
    group_b = factory.group(trainer_b, [shared])
    puzzle = factory.puzzle()

    make_assignment(tdb, trainer_b, group_b, [puzzle], [shared])
    session_b = factory.session(trainer_b, group_b, now() - timedelta(days=1))
    tdb.add(SessionAttendance(session_id=session_b.id, student_id=shared.id, status="present"))
    tdb.flush()

    seen_by_a = api.get(f"/trainer/students/{shared.id}/performance", headers=headers(user_a)).json()
    seen_by_b = api.get(f"/trainer/students/{shared.id}/performance", headers=headers(user_b)).json()

    assert seen_by_a["metrics"]["assignments_received"] == 0
    assert seen_by_a["metrics"]["sessions_recorded"] == 0
    assert seen_by_a["assignments"] == []
    assert seen_by_a["groups"] == [{"id": str(group_a.id), "name": group_a.name}]
    assert seen_by_b["metrics"]["assignments_received"] == 1
    assert seen_by_b["metrics"]["sessions_recorded"] == 1


def test_dashboard_counts_are_from_database(api, tdb, factory):
    user, trainer = factory.trainer()
    _, other = factory.trainer()
    students = [factory.student(trainer) for _ in range(3)]
    factory.group(trainer, students[:2])
    group = factory.group(trainer, students[1:])  # one student in both groups
    factory.group(other, [factory.student(other)])
    factory.puzzle(owner=trainer, status="draft")
    make_assignment(tdb, trainer, group, [factory.puzzle()], students[1:])
    factory.session(trainer, group, now() + timedelta(days=1))
    factory.session(trainer, group, now() - timedelta(days=1), status="completed")
    factory.attempt(students[0], factory.puzzle(), True)

    body = api.get("/trainer/dashboard", headers=headers(user)).json()

    assert body["summary"] == {
        "group_count": 2,
        "student_count": 3,
        "puzzles_created": 1,
        "active_assignments": 1,
        "upcoming_sessions": 1,
        "completed_sessions": 1,
    }
    assert body["performance"]["attempts"] == 1
    assert body["performance"]["accuracy_percent"] == 100.0
    assert len(body["upcoming_sessions"]) == 1
    assert len(body["recent_completed_sessions"]) == 1
    assert body["recent_activity"][0]["student_id"] == str(students[0].id)
