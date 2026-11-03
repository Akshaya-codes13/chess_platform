"""Import puzzles from the Lichess puzzle database (CC0).

Usage (inside the backend container):

    python -m scripts.import_lichess_puzzles path/to/lichess_db_puzzle.csv \
        --limit 200 [--min-rating 600] [--max-rating 2400] [--per-difficulty 70]

Input is the decompressed CSV from https://database.lichess.org/#puzzles
with the header ``PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,
NbPlays,Themes,GameUrl,OpeningTags``.

Lichess conventions differ from ours: the CSV's FEN is the position *before*
the opponent's move, and the first UCI move in ``Moves`` is that move. The
importer plays it, stores the resulting position as the puzzle FEN and the
remaining moves as the solution (student move first), then validates the
whole line with the same rules the API uses.

The import is idempotent: the same rows are selected on every run, puzzles
whose ``lichess_id`` already exists are skipped (but still count towards
``--limit``), and nothing is ever updated or deleted.
"""

import argparse
import csv
import re
import sys

import chess
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Puzzle, PuzzleCategory, PuzzleTheme, PuzzleThemeMapping
from app.services import puzzle_solver

# Lichess tags that describe the puzzle's length or source, not its tactic.
IGNORED_THEMES = {
    "short", "long", "veryLong", "oneMove", "master", "masterVsMaster",
    "superGM", "crushing", "advantage", "equality", "mate",
}
# Lichess tag -> existing theme slug, where the academy already has one.
THEME_ALIASES = {
    "discoveredAttack": "discovered-attack",
    "mateIn1": "checkmate",
    "mateIn2": "checkmate",
    "mateIn3": "checkmate",
}


def difficulty_for(rating: int) -> str:
    if rating < 1200:
        return "beginner"
    if rating < 1800:
        return "intermediate"
    return "advanced"


def theme_slug(tag: str) -> str:
    return THEME_ALIASES.get(tag) or re.sub(r"(?<!^)(?=[A-Z0-9])", "-", tag).lower()


def theme_name(tag: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z0-9])", " ", tag)
    return words[:1].upper() + words[1:]


def convert(row: dict) -> dict:
    """Turn one CSV row into puzzle fields. Raises ValueError if invalid."""
    board = chess.Board(row["FEN"])
    moves = row["Moves"].split()

    if len(moves) < 2:
        raise ValueError("needs the opponent's move and at least one reply")

    setup = chess.Move.from_uci(moves[0])
    if setup not in board.legal_moves:
        raise ValueError(f"setup move {moves[0]} is illegal")

    board.push(setup)
    fen = board.fen()
    solution = " ".join(moves[1:])

    try:
        puzzle_solver.load_puzzle(fen, solution)
    except puzzle_solver.InvalidPuzzleError as exc:
        raise ValueError(str(exc)) from exc

    rating = int(row["Rating"])

    return {
        "lichess_id": row["PuzzleId"],
        "fen": fen,
        "solution": solution,
        "rating": rating,
        "rating_deviation": int(row["RatingDeviation"]) if row.get("RatingDeviation") else None,
        "popularity": int(row["Popularity"]) if row.get("Popularity") else None,
        "difficulty": difficulty_for(rating),
        "themes": [tag for tag in (row.get("Themes") or "").split() if tag not in IGNORED_THEMES],
        "game_url": row.get("GameUrl") or None,
    }


def _theme(db: Session, cache: dict, tag: str) -> PuzzleTheme:
    slug = theme_slug(tag)
    if slug not in cache:
        theme = db.scalar(select(PuzzleTheme).where(PuzzleTheme.slug == slug))
        if theme is None:
            theme = PuzzleTheme(name=theme_name(tag)[:100], slug=slug)
            db.add(theme)
            db.flush()
        cache[slug] = theme
    return cache[slug]


def import_rows(
    db: Session,
    rows,
    limit: int,
    min_rating: int = 0,
    max_rating: int = 4000,
    per_difficulty: int | None = None,
) -> dict:
    categories = {c.slug: c for c in db.scalars(select(PuzzleCategory))}
    existing = set(db.scalars(select(Puzzle.lichess_id).where(Puzzle.lichess_id.is_not(None))))
    themes: dict = {}
    per_band: dict[str, int] = {}
    stats = {"imported": 0, "skipped_existing": 0, "skipped_invalid": 0, "skipped_filtered": 0}

    # Puzzles already imported from these rows count towards ``limit`` and
    # ``per_difficulty``, so running the same command twice adds nothing.
    selected = 0

    for row in rows:
        if selected >= limit:
            break

        try:
            data = convert(row)
        except (ValueError, KeyError) as exc:
            stats["skipped_invalid"] += 1
            print(f"Skipped {row.get('PuzzleId')}: {exc}", file=sys.stderr)
            continue

        band = data["difficulty"]
        if not (min_rating <= data["rating"] <= max_rating) or (
            per_difficulty is not None and per_band.get(band, 0) >= per_difficulty
        ):
            stats["skipped_filtered"] += 1
            continue

        selected += 1
        per_band[band] = per_band.get(band, 0) + 1

        if data["lichess_id"] in existing:
            stats["skipped_existing"] += 1
            continue

        category = categories.get(band)
        explanation = "Imported from the Lichess puzzle database (CC0)."
        if data["game_url"]:
            explanation += f" Source game: {data['game_url']}"

        puzzle = Puzzle(
            lichess_id=data["lichess_id"],
            fen=data["fen"],
            solution=data["solution"],
            rating=data["rating"],
            rating_deviation=data["rating_deviation"],
            popularity=data["popularity"],
            difficulty=band,
            category_id=category.id if category else None,
            source="lichess",
            type="puzzle",
            status="published",
            explanation=explanation,
        )
        db.add(puzzle)
        db.flush()

        # One mapping per theme, even when several tags share a slug.
        for tag in {theme_slug(tag): tag for tag in data["themes"]}.values():
            db.add(PuzzleThemeMapping(puzzle_id=puzzle.id, theme_id=_theme(db, themes, tag).id))

        existing.add(data["lichess_id"])
        stats["imported"] += 1

    db.commit()
    stats["by_difficulty"] = per_band
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("csv_path")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--min-rating", type=int, default=0)
    parser.add_argument("--max-rating", type=int, default=4000)
    parser.add_argument("--per-difficulty", type=int, default=None)
    args = parser.parse_args()

    with open(args.csv_path, newline="", encoding="utf-8") as handle, SessionLocal() as db:
        stats = import_rows(
            db,
            csv.DictReader(handle),
            limit=args.limit,
            min_rating=args.min_rating,
            max_rating=args.max_rating,
            per_difficulty=args.per_difficulty,
        )

    print(stats)


if __name__ == "__main__":
    main()
