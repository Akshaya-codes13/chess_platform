"""Trainer puzzle management and chess validation."""

import pytest
from sqlalchemy import select

from app.models import PuzzleCategory, PuzzleTheme, PuzzleThemeMapping
from app.services.chess_validation import validate_trainer_puzzle
from tests.trainer_fixtures import *  # noqa: F401,F403
from tests.trainer_fixtures import FORK, MATE_IN_ONE, headers


@pytest.fixture()
def taxonomy(tdb):
    category = PuzzleCategory(name="M5 Test Category", slug="m5-test-category")
    themes = [PuzzleTheme(name=f"M5 Theme {i}", slug=f"m5-theme-{i}") for i in range(2)]
    tdb.add_all([category, *themes])
    tdb.flush()
    return category, themes


def puzzle_payload(**overrides):
    fen, solution = MATE_IN_ONE
    return {"fen": fen, "solution": solution, "rating": 800, "difficulty": "beginner", **overrides}


def test_create_valid_puzzle(api, factory, tdb, taxonomy):
    user, trainer = factory.trainer()
    category, themes = taxonomy

    response = api.post(
        "/trainer/puzzles",
        json=puzzle_payload(
            solution="  G6G7 ",
            category_id=str(category.id),
            theme_ids=[str(theme.id) for theme in themes],
        ),
        headers=headers(user),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["is_owner"] is True
    assert body["solution"] == "g6g7"
    assert body["side_to_move"] == "white"
    assert body["category"]["slug"] == "m5-test-category"
    assert {theme["slug"] for theme in body["themes"]} == {"m5-theme-0", "m5-theme-1"}
    assert body["solution_locked"] is False


@pytest.mark.parametrize("fen", [
    "not a fen",
    "8/8/8/8/8/8/8/8 w - - 0 1",           # no kings
    "7k/8/5KQ1/8/8/8/8/8 w - - 0",          # truncated
    "kk6/8/8/8/8/8/8/7K w - - 0 1",         # two black kings
])
def test_reject_invalid_fen(api, factory, fen):
    user, _ = factory.trainer()

    response = api.post("/trainer/puzzles", json=puzzle_payload(fen=fen), headers=headers(user))

    assert response.status_code == 422


@pytest.mark.parametrize("solution", [
    "g6e5",            # not a queen move
    "e2e4",            # no piece on e2
    "g6g7 h8g8",       # continues after Qg7 is already mate
    "g6h6 h8g8 h6g7 g8g7",  # Qg7 is mate (defended by Kf6); Kxg7 is illegal
    "zz99",            # not UCI
])
def test_reject_illegal_or_invalid_solution(api, factory, solution):
    user, _ = factory.trainer()

    response = api.post("/trainer/puzzles", json=puzzle_payload(solution=solution), headers=headers(user))

    assert response.status_code == 422, response.text


def test_reject_starting_position_already_mated():
    with pytest.raises(ValueError, match="already game over"):
        validate_trainer_puzzle("7k/6Q1/5K2/8/8/8/8/8 b - - 0 1", "h8g8")


def test_validate_endpoint_reports_without_saving(api, factory):
    user, _ = factory.trainer()
    fen, solution = MATE_IN_ONE

    ok = api.post("/trainer/puzzles/validate", json={"fen": fen, "solution": solution}, headers=headers(user)).json()
    bad = api.post("/trainer/puzzles/validate", json={"fen": fen, "solution": "a1a2"}, headers=headers(user)).json()

    assert ok["valid"] is True and ok["ends_in_checkmate"] is True and ok["move_count"] == 1
    assert bad["valid"] is False and "a1a2" in bad["error"]


def test_reject_unknown_theme_or_category(api, factory, taxonomy):
    user, _ = factory.trainer()
    import uuid

    unknown_theme = api.post(
        "/trainer/puzzles", json=puzzle_payload(theme_ids=[str(uuid.uuid4())]), headers=headers(user)
    )
    unknown_category = api.post(
        "/trainer/puzzles", json=puzzle_payload(category_id=str(uuid.uuid4())), headers=headers(user)
    )
    category, themes = taxonomy
    duplicate_theme = api.post(
        "/trainer/puzzles",
        json=puzzle_payload(theme_ids=[str(themes[0].id), str(themes[0].id)]),
        headers=headers(user),
    )

    assert unknown_theme.status_code == 422
    assert unknown_category.status_code == 422
    assert duplicate_theme.status_code == 422


def test_update_replaces_theme_mappings(api, factory, tdb, taxonomy):
    user, trainer = factory.trainer()
    _, themes = taxonomy
    created = api.post(
        "/trainer/puzzles", json=puzzle_payload(theme_ids=[str(themes[0].id)]), headers=headers(user)
    ).json()

    response = api.patch(
        f"/trainer/puzzles/{created['id']}", json={"theme_ids": [str(themes[1].id)]}, headers=headers(user)
    )

    assert response.status_code == 200
    mapped = set(tdb.scalars(select(PuzzleThemeMapping.theme_id).where(PuzzleThemeMapping.puzzle_id == created["id"])))
    assert mapped == {themes[1].id}


def test_trainer_cannot_edit_another_trainers_puzzle(api, factory):
    user_a, _ = factory.trainer()
    _, trainer_b = factory.trainer()
    published = factory.puzzle(owner=trainer_b, status="published")
    draft = factory.puzzle(owner=trainer_b, status="draft")

    # Published puzzles are readable but not editable; drafts are invisible.
    assert api.get(f"/trainer/puzzles/{published.id}", headers=headers(user_a)).status_code == 200
    assert api.patch(f"/trainer/puzzles/{published.id}", json={"rating": 1}, headers=headers(user_a)).status_code == 403
    assert api.post(f"/trainer/puzzles/{published.id}/archive", headers=headers(user_a)).status_code == 403
    assert api.get(f"/trainer/puzzles/{draft.id}", headers=headers(user_a)).status_code == 404


def test_library_puzzles_are_read_only(api, factory):
    user, _ = factory.trainer()
    library = factory.puzzle(owner=None)

    assert api.patch(f"/trainer/puzzles/{library.id}", json={"rating": 5}, headers=headers(user)).status_code == 403


def test_list_filters_and_visibility(api, factory):
    user, trainer = factory.trainer()
    _, other = factory.trainer()
    mine = factory.puzzle(owner=trainer, status="draft", rating=1500)
    factory.puzzle(owner=other, status="draft", rating=1500)

    body = api.get(
        "/trainer/puzzles", params={"ownership": "mine"}, headers=headers(user)
    ).json()
    assert [p["id"] for p in body["items"]] == [str(mine.id)]

    rated = api.get(
        "/trainer/puzzles",
        params={"rating_min": 1400, "rating_max": 1600, "status": "draft"},
        headers=headers(user),
    ).json()
    assert [p["id"] for p in rated["items"]] == [str(mine.id)]


def test_status_transitions(api, factory):
    user, trainer = factory.trainer()
    puzzle = factory.puzzle(owner=trainer, status="draft")
    url = f"/trainer/puzzles/{puzzle.id}"

    assert api.post(f"{url}/publish", headers=headers(user)).json()["status"] == "published"
    assert api.post(f"{url}/publish", headers=headers(user)).status_code == 409
    assert api.post(f"{url}/archive", headers=headers(user)).json()["status"] == "archived"
    assert api.patch(url, json={"rating": 1200}, headers=headers(user)).status_code == 409
    assert api.post(f"{url}/restore", headers=headers(user)).json()["status"] == "draft"


def test_solution_locked_once_attempted(api, factory):
    user, trainer = factory.trainer()
    puzzle = factory.puzzle(owner=trainer, status="published")
    factory.attempt(factory.student(trainer), puzzle, solved=True)
    fen, solution = FORK

    response = api.patch(
        f"/trainer/puzzles/{puzzle.id}", json={"fen": fen, "solution": solution}, headers=headers(user)
    )
    detail = api.get(f"/trainer/puzzles/{puzzle.id}", headers=headers(user)).json()

    assert response.status_code == 409
    assert detail["solution_locked"] is True
    assert api.patch(f"/trainer/puzzles/{puzzle.id}", json={"rating": 1111}, headers=headers(user)).status_code == 200
