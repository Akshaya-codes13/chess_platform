"""M9 PGN game library: databases, folders, breadcrumbs, import, replay and
access rules."""

from tests.student_world import *  # noqa: F401,F403
from tests.student_world import _user, auth_headers

TWO_GAMES = """[Event "Club Championship"]
[Site "Chennai"]
[Date "2024.05.01"]
[Round "1"]
[White "Anand, V"]
[Black "Carlsen, M"]
[Result "1-0"]
[WhiteElo "2750"]
[BlackElo "2830"]
[ECO "C65"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 Nf6 4. O-O Nxe4 5. Re1 Nd6 1-0

[Event "Blitz"]
[White "Student"]
[Black "Trainer"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""

ILLEGAL = """[Event "Broken"]
[White "A"]
[Black "B"]
[Result "*"]

1. e4 e5 2. Ke3 Ke6 3. Qxh8 *
"""


def make_db(api, headers, **body):
    response = api.post("/games/databases", json={"name": "My games", **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def import_text(api, headers, database_id, pgn, folder_id=None):
    data = {"pgn": pgn}
    if folder_id:
        data["folder_id"] = folder_id
    return api.post(f"/games/databases/{database_id}/import", data=data, headers=headers)


def test_upload_browse_and_replay(api, world):
    headers = world.trainer_headers
    database = make_db(api, headers)

    folder = api.post(f"/games/databases/{database['id']}/folders", json={"name": "Openings"}, headers=headers).json()
    sub = api.post(
        f"/games/databases/{database['id']}/folders",
        json={"name": "Ruy Lopez", "parent_id": folder["id"]},
        headers=headers,
    ).json()

    result = import_text(api, headers, database["id"], TWO_GAMES, sub["id"])
    assert result.status_code == 200, result.text
    assert result.json()["imported"] == 2 and result.json()["skipped"] == 0

    browse = api.get(
        f"/games/databases/{database['id']}/browse", params={"folder_id": sub["id"]}, headers=headers
    ).json()
    assert [crumb["name"] for crumb in browse["breadcrumbs"]] == ["My games", "Openings", "Ruy Lopez"]
    assert browse["games"]["total"] == 2

    root = api.get(f"/games/databases/{database['id']}/browse", headers=headers).json()
    assert root["folders"] == [{"id": folder["id"], "name": "Openings", "game_count": 0}]
    assert root["games"]["total"] == 0

    found = api.get(f"/games/databases/{database['id']}/browse", params={"search": "carlsen"}, headers=headers).json()
    assert found["games"]["total"] == 1

    game_id = next(g["id"] for g in browse["games"]["items"] if g["white"] == "Anand, V")
    game = api.get(f"/games/{game_id}", headers=headers).json()
    assert game["moves"][:3] == ["e4", "e5", "Nf3"]
    assert game["ply_count"] == 10 and len(game["positions"]) == 11
    assert game["positions"][1]["uci"] == "e2e4"
    assert game["white_elo"] == 2750 and game["eco"] == "C65" and game["event"] == "Club Championship"
    assert "Nxe4" in game["pgn"]
    assert [crumb["name"] for crumb in game["breadcrumbs"]][-1] == "Ruy Lopez"


def test_file_upload_and_invalid_games(api, world):
    headers = world.trainer_headers
    database = make_db(api, headers)

    upload = api.post(
        f"/games/databases/{database['id']}/import",
        files={"file": ("games.pgn", (TWO_GAMES + "\n" + ILLEGAL).encode(), "application/x-chess-pgn")},
        headers=headers,
    )
    assert upload.status_code == 200
    assert upload.json()["imported"] == 2 and upload.json()["skipped"] == 1

    only_bad = import_text(api, headers, database["id"], ILLEGAL)
    assert only_bad.status_code == 422

    empty = import_text(api, headers, database["id"], "   ")
    assert empty.status_code == 422

    missing = api.post(f"/games/databases/{database['id']}/import", data={}, headers=headers)
    assert missing.status_code == 422


def test_private_and_shared_access(api, world):
    trainer = world.trainer_headers
    private = make_db(api, trainer, name="Private prep")
    shared = make_db(api, trainer, name="Class games", is_shared=True)
    import_text(api, trainer, shared["id"], TWO_GAMES)

    student = world.headers["a"]
    names = {item["name"] for item in api.get("/games/databases", headers=student).json()}
    assert "Class games" in names and "Private prep" not in names

    assert api.get(f"/games/databases/{private['id']}/browse", headers=student).status_code == 404
    shared_view = api.get(f"/games/databases/{shared['id']}/browse", headers=student).json()
    assert shared_view["database"]["can_edit"] is False
    game_id = shared_view["games"]["items"][0]["id"]
    assert api.get(f"/games/{game_id}", headers=student).status_code == 200

    # Readers cannot change a shared database.
    assert import_text(api, student, shared["id"], TWO_GAMES).status_code == 403
    assert api.delete(f"/games/{game_id}", headers=student).status_code == 403

    # Students may keep private databases but cannot share them.
    assert api.post("/games/databases", json={"name": "Mine", "is_shared": True}, headers=student).status_code == 403
    own = make_db(api, student, name="Mine")
    assert import_text(api, student, own["id"], TWO_GAMES).json()["imported"] == 2


def test_admin_can_manage_any_database(api, world):
    admin = _user(world.db, "admin", "Admin")
    database = make_db(api, world.trainer_headers, name="Trainer DB")
    renamed = api.patch(f"/games/databases/{database['id']}", json={"name": "Renamed"}, headers=auth_headers(admin))
    assert renamed.status_code == 200 and renamed.json()["name"] == "Renamed"


def test_folder_rules(api, world):
    headers = world.trainer_headers
    database = make_db(api, headers)
    url = f"/games/databases/{database['id']}/folders"

    folder = api.post(url, json={"name": "Endgames"}, headers=headers).json()
    assert api.post(url, json={"name": "endgames"}, headers=headers).status_code == 409

    import_text(api, headers, database["id"], TWO_GAMES, folder["id"])
    assert api.delete(f"/games/folders/{folder['id']}", headers=headers).status_code == 409
    assert api.delete(f"/games/databases/{database['id']}", headers=headers).status_code == 409

    games = api.get(
        f"/games/databases/{database['id']}/browse", params={"folder_id": folder["id"]}, headers=headers
    ).json()["games"]["items"]
    for game in games:
        moved = api.patch(f"/games/{game['id']}", json={"folder_id": None}, headers=headers)
        assert moved.status_code == 200 and moved.json()["folder_id"] is None

    assert api.delete(f"/games/folders/{folder['id']}", headers=headers).status_code == 204

    other = make_db(api, headers, name="Other")
    other_folder = api.post(f"/games/databases/{other['id']}/folders", json={"name": "X"}, headers=headers).json()
    assert api.patch(f"/games/{games[0]['id']}", json={"folder_id": other_folder["id"]}, headers=headers).status_code == 422
