"""PGN game library: databases, nested folders and imported games.

Access rules:

* Every signed-in user can create private databases and import PGN into them.
* A shared database (``is_shared``) is readable by every signed-in user.
  Only admins and trainers can share a database.
* Only the owner, or an admin, can change a database, its folders or games.
* Anything a user may not read raises ``NotFoundError``, like a missing ID.

PGN is parsed with python-chess. Every move is replayed, so a stored game is
always legal from its start position; games with errors are reported and
skipped, the rest of the file is still imported.
"""

import io
import uuid

import chess
import chess.pgn
from sqlalchemy import exists, func, or_, select, true
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models import GameDatabase, GameFolder, PgnGame, User
from app.utils.pagination import PageParams, make_page, paginate

MAX_PGN_BYTES = 2 * 1024 * 1024
MAX_GAMES_PER_IMPORT = 500
MAX_FOLDER_DEPTH = 8
RESULTS = ("1-0", "0-1", "1/2-1/2", "*")


# --- Access ------------------------------------------------------------------


def _can_write(user: User, database: GameDatabase) -> bool:
    return user.role == "admin" or database.owner_id == user.id


def _readable(user: User):
    if user.role == "admin":
        return true()
    return or_(GameDatabase.owner_id == user.id, GameDatabase.is_shared.is_(True))


def get_database(db: Session, user: User, database_id: uuid.UUID, write: bool = False) -> GameDatabase:
    database = db.scalar(select(GameDatabase).where(GameDatabase.id == database_id, _readable(user)))

    if database is None:
        raise NotFoundError("Game database not found.")
    if write and not _can_write(user, database):
        raise PermissionDeniedError("Only the owner can change this database.")

    return database


def _get_folder(db: Session, user: User, folder_id: uuid.UUID, write: bool = False) -> GameFolder:
    folder = db.get(GameFolder, folder_id)

    if folder is None:
        raise NotFoundError("Folder not found.")

    get_database(db, user, folder.database_id, write=write)
    return folder


def _get_game(db: Session, user: User, game_id: uuid.UUID, write: bool = False) -> PgnGame:
    game = db.get(PgnGame, game_id)

    if game is None:
        raise NotFoundError("Game not found.")

    get_database(db, user, game.database_id, write=write)
    return game


def _check_share(user: User, is_shared: bool | None) -> None:
    if is_shared and user.role not in ("admin", "trainer"):
        raise PermissionDeniedError("Only trainers and admins can share a database.")


# --- Databases ---------------------------------------------------------------


def _database_item(database: GameDatabase, owner_name: str, game_count: int, user: User) -> dict:
    return {
        "id": database.id,
        "name": database.name,
        "description": database.description,
        "is_shared": database.is_shared,
        "owner_id": database.owner_id,
        "owner_name": owner_name,
        "game_count": game_count,
        "can_edit": _can_write(user, database),
        "created_at": database.created_at,
    }


def list_databases(db: Session, user: User) -> list[dict]:
    counts = (
        select(PgnGame.database_id, func.count().label("games"))
        .group_by(PgnGame.database_id)
        .subquery()
    )
    rows = db.execute(
        select(GameDatabase, User.full_name, func.coalesce(counts.c.games, 0))
        .join(User, User.id == GameDatabase.owner_id)
        .outerjoin(counts, counts.c.database_id == GameDatabase.id)
        .where(_readable(user))
        .order_by(GameDatabase.name)
    ).all()
    return [_database_item(database, name, count, user) for database, name, count in rows]


def create_database(db: Session, user: User, data: dict) -> dict:
    _check_share(user, data.get("is_shared"))
    database = GameDatabase(
        owner_id=user.id,
        name=data["name"].strip(),
        description=data.get("description"),
        is_shared=bool(data.get("is_shared")),
    )
    db.add(database)
    db.commit()
    return _database_item(database, user.full_name, 0, user)


def update_database(db: Session, user: User, database_id: uuid.UUID, changes: dict) -> dict:
    database = get_database(db, user, database_id, write=True)
    _check_share(user, changes.get("is_shared"))

    if changes.get("name"):
        database.name = changes["name"].strip()
    if "description" in changes:
        database.description = changes["description"]
    if changes.get("is_shared") is not None:
        database.is_shared = changes["is_shared"]

    db.commit()
    return _database_detail(db, user, database)


def delete_database(db: Session, user: User, database_id: uuid.UUID) -> None:
    database = get_database(db, user, database_id, write=True)

    if db.scalar(select(exists().where(PgnGame.database_id == database.id))):
        raise ConflictError("Delete or move this database's games first.")

    for folder in db.scalars(
        select(GameFolder).where(GameFolder.database_id == database.id).order_by(GameFolder.created_at.desc())
    ):
        folder.parent_id = None
    db.flush()
    db.delete(database)
    db.commit()


def _database_detail(db: Session, user: User, database: GameDatabase) -> dict:
    owner_name = db.scalar(select(User.full_name).where(User.id == database.owner_id))
    count = db.scalar(select(func.count()).where(PgnGame.database_id == database.id)) or 0
    return _database_item(database, owner_name, count, user)


# --- Folders and browsing ----------------------------------------------------


def _breadcrumbs(db: Session, database: GameDatabase, folder: GameFolder | None) -> list[dict]:
    trail = []
    current = folder

    while current is not None:
        trail.append({"id": current.id, "name": current.name})
        current = db.get(GameFolder, current.parent_id) if current.parent_id else None

    return [{"id": None, "name": database.name}] + list(reversed(trail))


def browse(
    db: Session,
    user: User,
    database_id: uuid.UUID,
    folder_id: uuid.UUID | None,
    search: str | None,
    params: PageParams,
) -> dict:
    """A folder's subfolders and games. With ``search``, games anywhere in
    the database whose players or event match."""
    database = get_database(db, user, database_id)
    folder = None

    if folder_id is not None:
        folder = _get_folder(db, user, folder_id)
        if folder.database_id != database.id:
            raise NotFoundError("Folder not found.")

    folder_counts = (
        select(PgnGame.folder_id, func.count().label("games")).group_by(PgnGame.folder_id).subquery()
    )
    folders = db.execute(
        select(GameFolder, func.coalesce(folder_counts.c.games, 0))
        .outerjoin(folder_counts, folder_counts.c.folder_id == GameFolder.id)
        .where(
            GameFolder.database_id == database.id,
            GameFolder.parent_id == folder.id if folder else GameFolder.parent_id.is_(None),
        )
        .order_by(GameFolder.name)
    ).all()

    games_query = select(PgnGame).where(PgnGame.database_id == database.id)

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        games_query = games_query.where(
            or_(PgnGame.white.ilike(pattern), PgnGame.black.ilike(pattern), PgnGame.event.ilike(pattern))
        )
    else:
        games_query = games_query.where(
            PgnGame.folder_id == folder.id if folder else PgnGame.folder_id.is_(None)
        )

    rows, total = paginate(db, games_query.order_by(PgnGame.created_at.desc(), PgnGame.id), params)

    return {
        "database": _database_detail(db, user, database),
        "folder": {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id} if folder else None,
        "breadcrumbs": _breadcrumbs(db, database, folder),
        "folders": [
            {"id": child.id, "name": child.name, "game_count": count} for child, count in folders
        ],
        "games": make_page([_game_summary(row[0]) for row in rows], total, params),
    }


def _depth(db: Session, folder: GameFolder | None) -> int:
    depth = 0
    while folder is not None:
        depth += 1
        folder = db.get(GameFolder, folder.parent_id) if folder.parent_id else None
    return depth


def create_folder(db: Session, user: User, database_id: uuid.UUID, data: dict) -> dict:
    database = get_database(db, user, database_id, write=True)
    parent = None

    if data.get("parent_id"):
        parent = _get_folder(db, user, data["parent_id"], write=True)
        if parent.database_id != database.id:
            raise ValidationError("The parent folder belongs to another database.")
        if _depth(db, parent) >= MAX_FOLDER_DEPTH:
            raise ValidationError(f"Folders can be nested at most {MAX_FOLDER_DEPTH} levels deep.")

    name = data["name"].strip()
    _check_unique_name(db, database.id, parent.id if parent else None, name)

    folder = GameFolder(database_id=database.id, parent_id=parent.id if parent else None, name=name)
    db.add(folder)
    db.commit()
    return {"id": folder.id, "name": folder.name, "game_count": 0}


def _check_unique_name(db: Session, database_id, parent_id, name: str, exclude_id=None) -> None:
    query = select(GameFolder.id).where(
        GameFolder.database_id == database_id,
        func.lower(GameFolder.name) == name.lower(),
        GameFolder.parent_id == parent_id if parent_id else GameFolder.parent_id.is_(None),
    )
    if exclude_id:
        query = query.where(GameFolder.id != exclude_id)
    if db.scalar(query):
        raise ConflictError("A folder with this name already exists here.")


def rename_folder(db: Session, user: User, folder_id: uuid.UUID, name: str) -> dict:
    folder = _get_folder(db, user, folder_id, write=True)
    _check_unique_name(db, folder.database_id, folder.parent_id, name.strip(), exclude_id=folder.id)
    folder.name = name.strip()
    db.commit()
    count = db.scalar(select(func.count()).where(PgnGame.folder_id == folder.id)) or 0
    return {"id": folder.id, "name": folder.name, "game_count": count}


def delete_folder(db: Session, user: User, folder_id: uuid.UUID) -> None:
    folder = _get_folder(db, user, folder_id, write=True)

    has_children = db.scalar(select(exists().where(GameFolder.parent_id == folder.id)))
    has_games = db.scalar(select(exists().where(PgnGame.folder_id == folder.id)))

    if has_children or has_games:
        raise ConflictError("Only empty folders can be deleted.")

    db.delete(folder)
    db.commit()


# --- PGN import --------------------------------------------------------------


def _int_header(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() and len(value) <= 5 else None


def _clean(value: str | None, limit: int) -> str | None:
    if not value or value in ("?", "????.??.??"):
        return None
    return value[:limit]


def parse_pgn(text: str) -> tuple[list[dict], list[dict]]:
    """Parse every game in ``text``. Returns (games, errors)."""
    stream = io.StringIO(text)
    games, errors = [], []
    index = 0

    while True:
        try:
            game = chess.pgn.read_game(stream)
        except (ValueError, IndexError) as exc:  # malformed headers
            errors.append({"index": index + 1, "error": f"Could not read game: {exc}"})
            break

        if game is None:
            break

        index += 1

        if index > MAX_GAMES_PER_IMPORT:
            errors.append({"index": index, "error": f"Only the first {MAX_GAMES_PER_IMPORT} games are imported."})
            break

        if game.errors:
            errors.append({"index": index, "error": str(game.errors[0])})
            continue

        board = game.board()
        start_fen = board.fen()
        moves = []

        for move in game.mainline_moves():
            moves.append(board.san(move))
            board.push(move)

        if not moves and not game.headers.get("FEN"):
            errors.append({"index": index, "error": "The game has no moves."})
            continue

        headers = dict(game.headers)
        result = headers.get("Result", "*")
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)

        games.append(
            {
                "white": _clean(headers.get("White"), 150) or "Unknown",
                "black": _clean(headers.get("Black"), 150) or "Unknown",
                "result": result if result in RESULTS else "*",
                "event": _clean(headers.get("Event"), 200),
                "site": _clean(headers.get("Site"), 200),
                "game_date": _clean(headers.get("Date"), 20),
                "round": _clean(headers.get("Round"), 20),
                "eco": _clean(headers.get("ECO"), 10),
                "white_elo": _int_header(headers.get("WhiteElo")),
                "black_elo": _int_header(headers.get("BlackElo")),
                "initial_fen": start_fen if start_fen != chess.STARTING_FEN else None,
                "moves": moves,
                "ply_count": len(moves),
                "headers": {key: value[:500] for key, value in headers.items()},
                "pgn": game.accept(exporter),
            }
        )

    return games, errors


def import_pgn(
    db: Session,
    user: User,
    database_id: uuid.UUID,
    folder_id: uuid.UUID | None,
    raw: bytes,
) -> dict:
    database = get_database(db, user, database_id, write=True)

    if folder_id is not None:
        folder = _get_folder(db, user, folder_id, write=True)
        if folder.database_id != database.id:
            raise ValidationError("The folder belongs to another database.")

    if len(raw) > MAX_PGN_BYTES:
        raise ValidationError(f"PGN files can be at most {MAX_PGN_BYTES // (1024 * 1024)} MB.")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    if not text.strip():
        raise ValidationError("The PGN is empty.")

    parsed, errors = parse_pgn(text)

    if not parsed:
        detail = errors[0]["error"] if errors else "No games found."
        raise ValidationError(f"No valid games could be imported. {detail}")

    created = []
    for data in parsed:
        game = PgnGame(database_id=database.id, folder_id=folder_id, uploaded_by=user.id, **data)
        db.add(game)
        created.append(game)

    db.commit()

    return {
        "imported": len(created),
        "skipped": len(errors),
        "errors": errors[:20],
        "games": [_game_summary(game) for game in created[:50]],
    }


# --- Games -------------------------------------------------------------------


def _game_summary(game: PgnGame) -> dict:
    return {
        "id": game.id,
        "database_id": game.database_id,
        "folder_id": game.folder_id,
        "white": game.white,
        "black": game.black,
        "result": game.result,
        "event": game.event,
        "game_date": game.game_date,
        "eco": game.eco,
        "white_elo": game.white_elo,
        "black_elo": game.black_elo,
        "ply_count": game.ply_count,
        "created_at": game.created_at,
    }


def get_game(db: Session, user: User, game_id: uuid.UUID) -> dict:
    """The game with every position, so clients can replay it directly."""
    game = _get_game(db, user, game_id)
    database = db.get(GameDatabase, game.database_id)
    folder = db.get(GameFolder, game.folder_id) if game.folder_id else None

    board = chess.Board(game.initial_fen) if game.initial_fen else chess.Board()
    positions = [{"ply": 0, "san": None, "uci": None, "fen": board.fen()}]

    for ply, san in enumerate(game.moves, start=1):
        move = board.parse_san(san)
        board.push(move)
        positions.append({"ply": ply, "san": san, "uci": move.uci(), "fen": board.fen()})

    return {
        **_game_summary(game),
        "site": game.site,
        "round": game.round,
        "initial_fen": game.initial_fen or chess.STARTING_FEN,
        "headers": game.headers,
        "moves": game.moves,
        "positions": positions,
        "pgn": game.pgn,
        "can_edit": _can_write(user, database),
        "breadcrumbs": _breadcrumbs(db, database, folder),
    }


def move_game(db: Session, user: User, game_id: uuid.UUID, folder_id: uuid.UUID | None) -> dict:
    game = _get_game(db, user, game_id, write=True)

    if folder_id is not None:
        folder = _get_folder(db, user, folder_id, write=True)
        if folder.database_id != game.database_id:
            raise ValidationError("Games can only move to folders of their own database.")

    game.folder_id = folder_id
    db.commit()
    return _game_summary(game)


def delete_game(db: Session, user: User, game_id: uuid.UUID) -> None:
    game = _get_game(db, user, game_id, write=True)
    db.delete(game)
    db.commit()
