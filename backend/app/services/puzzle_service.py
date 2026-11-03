"""Trainer puzzle management.

Visibility: a trainer sees every published puzzle (library puzzles and
other trainers' published puzzles) plus all of their own puzzles in any
status. Only the author may edit, publish, unpublish or archive a puzzle;
library puzzles (no author) are read-only here.
"""

import uuid
from collections import defaultdict
from typing import Literal

import chess
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models import (
    AssignmentPuzzle,
    Puzzle,
    PuzzleAttempt,
    PuzzleCategory,
    PuzzleTheme,
    PuzzleThemeMapping,
    TrainerProfile,
)
from app.services.chess_validation import validate_trainer_puzzle
from app.services.trainer_access import like_pattern
from app.utils.pagination import PageParams, make_page, paginate

TRAINER_PUZZLE_SOURCE = "trainer"

PUZZLE_SORTS = {
    "-created_at": Puzzle.created_at.desc(),
    "created_at": Puzzle.created_at.asc(),
    "rating": Puzzle.rating.asc().nulls_last(),
    "-rating": Puzzle.rating.desc().nulls_last(),
}

Ownership = Literal["all", "mine", "library"]


def visible_to(trainer: TrainerProfile):
    return or_(
        Puzzle.created_by_trainer_id == trainer.id,
        Puzzle.status == "published",
    )


def _side_to_move(fen: str) -> str:
    return "white" if chess.Board(fen).turn == chess.WHITE else "black"


def _themes_by_puzzle(db: Session, puzzle_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    themes = defaultdict(list)

    if not puzzle_ids:
        return themes

    rows = db.execute(
        select(PuzzleThemeMapping.puzzle_id, PuzzleTheme.id, PuzzleTheme.name, PuzzleTheme.slug)
        .join(PuzzleTheme, PuzzleTheme.id == PuzzleThemeMapping.theme_id)
        .where(PuzzleThemeMapping.puzzle_id.in_(puzzle_ids))
        .order_by(PuzzleTheme.name)
    )

    for row in rows:
        themes[row.puzzle_id].append({"id": row.id, "name": row.name, "slug": row.slug})

    return themes


def _summary(puzzle: Puzzle, category, themes: list[dict], trainer: TrainerProfile) -> dict:
    return {
        "id": puzzle.id,
        "fen": puzzle.fen,
        "rating": puzzle.rating,
        "difficulty": puzzle.difficulty,
        "type": puzzle.type,
        "status": puzzle.status,
        "source": puzzle.source,
        "category": (
            {"id": category.id, "name": category.name, "slug": category.slug}
            if category else None
        ),
        "themes": themes,
        "is_owner": puzzle.created_by_trainer_id == trainer.id,
        "created_at": puzzle.created_at,
        "updated_at": puzzle.updated_at,
    }


def get_taxonomy(db: Session) -> dict:
    return {
        "categories": db.scalars(select(PuzzleCategory).order_by(PuzzleCategory.name)).all(),
        "themes": db.scalars(select(PuzzleTheme).order_by(PuzzleTheme.name)).all(),
    }


def list_puzzles(
    db: Session,
    trainer: TrainerProfile,
    params: PageParams,
    *,
    search: str | None = None,
    difficulty: str | None = None,
    category_id: uuid.UUID | None = None,
    theme_id: uuid.UUID | None = None,
    rating_min: int | None = None,
    rating_max: int | None = None,
    status: str | None = None,
    ownership: Ownership = "all",
    sort: str = "-created_at",
) -> dict:
    query = (
        select(Puzzle, PuzzleCategory)
        .outerjoin(PuzzleCategory, PuzzleCategory.id == Puzzle.category_id)
        .where(visible_to(trainer))
    )

    if ownership == "mine":
        query = query.where(Puzzle.created_by_trainer_id == trainer.id)
    elif ownership == "library":
        query = query.where(Puzzle.created_by_trainer_id.is_(None))

    if search and search.strip():
        pattern = like_pattern(search)
        query = query.where(
            or_(Puzzle.explanation.ilike(pattern), Puzzle.lichess_id.ilike(pattern))
        )
    if difficulty:
        query = query.where(Puzzle.difficulty == difficulty)
    if category_id:
        query = query.where(Puzzle.category_id == category_id)
    if theme_id:
        query = query.where(
            exists().where(
                PuzzleThemeMapping.puzzle_id == Puzzle.id,
                PuzzleThemeMapping.theme_id == theme_id,
            )
        )
    if rating_min is not None:
        query = query.where(Puzzle.rating >= rating_min)
    if rating_max is not None:
        query = query.where(Puzzle.rating <= rating_max)
    if status:
        query = query.where(Puzzle.status == status)

    query = query.order_by(PUZZLE_SORTS.get(sort, PUZZLE_SORTS["-created_at"]), Puzzle.id)

    rows, total = paginate(db, query, params)
    themes = _themes_by_puzzle(db, [puzzle.id for puzzle, _ in rows])

    items = [
        _summary(puzzle, category, themes[puzzle.id], trainer)
        for puzzle, category in rows
    ]
    return make_page(items, total, params)


def get_visible_puzzle(db: Session, trainer: TrainerProfile, puzzle_id: uuid.UUID) -> Puzzle:
    puzzle = db.scalar(select(Puzzle).where(Puzzle.id == puzzle_id, visible_to(trainer)))

    if puzzle is None:
        raise NotFoundError("Puzzle not found.")

    return puzzle


def get_owned_puzzle(db: Session, trainer: TrainerProfile, puzzle_id: uuid.UUID) -> Puzzle:
    puzzle = get_visible_puzzle(db, trainer, puzzle_id)

    if puzzle.created_by_trainer_id != trainer.id:
        raise PermissionDeniedError("You can only change puzzles you created.")

    return puzzle


def _usage_counts(db: Session, puzzle_id: uuid.UUID) -> tuple[int, int]:
    assignments = db.scalar(
        select(func.count()).where(AssignmentPuzzle.puzzle_id == puzzle_id)
    )
    attempts = db.scalar(
        select(func.count()).where(PuzzleAttempt.puzzle_id == puzzle_id)
    )
    return assignments or 0, attempts or 0


def puzzle_detail(db: Session, trainer: TrainerProfile, puzzle: Puzzle) -> dict:
    category = db.get(PuzzleCategory, puzzle.category_id) if puzzle.category_id else None
    themes = _themes_by_puzzle(db, [puzzle.id])[puzzle.id]
    assignment_count, attempt_count = _usage_counts(db, puzzle.id)

    return {
        **_summary(puzzle, category, themes, trainer),
        "solution": puzzle.solution,
        "explanation": puzzle.explanation,
        "side_to_move": _side_to_move(puzzle.fen),
        "assignment_count": assignment_count,
        "attempt_count": attempt_count,
        "solution_locked": bool(assignment_count or attempt_count),
    }


def get_puzzle(db: Session, trainer: TrainerProfile, puzzle_id: uuid.UUID) -> dict:
    return puzzle_detail(db, trainer, get_visible_puzzle(db, trainer, puzzle_id))


def validate_position(fen: str, solution: str) -> dict:
    """Dry-run validation for the puzzle editor; never raises for bad input."""
    try:
        fen, solution = validate_trainer_puzzle(fen, solution)
    except ValueError as exc:
        return {"valid": False, "error": str(exc)}

    board = chess.Board(fen)
    for uci in solution.split():
        board.push_uci(uci)

    return {
        "valid": True,
        "fen": fen,
        "solution": solution,
        "final_fen": board.fen(),
        "side_to_move": _side_to_move(fen),
        "move_count": len(solution.split()),
        "ends_in_checkmate": board.is_checkmate(),
    }


def _check_position(fen: str, solution: str) -> tuple[str, str]:
    try:
        return validate_trainer_puzzle(fen, solution)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _check_category(db: Session, category_id: uuid.UUID | None) -> None:
    if category_id is not None and db.get(PuzzleCategory, category_id) is None:
        raise ValidationError("Puzzle category not found.")


def _set_themes(db: Session, puzzle: Puzzle, theme_ids: list[uuid.UUID]) -> None:
    found = set(db.scalars(select(PuzzleTheme.id).where(PuzzleTheme.id.in_(theme_ids))))
    missing = set(theme_ids) - found

    if missing:
        raise ValidationError("One or more puzzle themes were not found.")

    current = {
        mapping.theme_id: mapping
        for mapping in db.scalars(
            select(PuzzleThemeMapping).where(PuzzleThemeMapping.puzzle_id == puzzle.id)
        )
    }

    for theme_id, mapping in current.items():
        if theme_id not in found:
            db.delete(mapping)

    for theme_id in theme_ids:
        if theme_id not in current:
            db.add(PuzzleThemeMapping(puzzle_id=puzzle.id, theme_id=theme_id))


def create_puzzle(db: Session, trainer: TrainerProfile, data: dict) -> dict:
    fen, solution = _check_position(data["fen"], data["solution"])
    _check_category(db, data.get("category_id"))

    puzzle = Puzzle(
        created_by_trainer_id=trainer.id,
        fen=fen,
        solution=solution,
        rating=data.get("rating"),
        difficulty=data.get("difficulty"),
        type=data.get("type") or "puzzle",
        category_id=data.get("category_id"),
        explanation=data.get("explanation"),
        source=TRAINER_PUZZLE_SOURCE,
        status="draft",
    )
    db.add(puzzle)
    db.flush()

    _set_themes(db, puzzle, data.get("theme_ids") or [])

    db.commit()
    db.refresh(puzzle)

    return puzzle_detail(db, trainer, puzzle)


def update_puzzle(db: Session, trainer: TrainerProfile, puzzle_id: uuid.UUID, changes: dict) -> dict:
    puzzle = get_owned_puzzle(db, trainer, puzzle_id)

    if puzzle.status == "archived":
        raise ConflictError("Archived puzzles cannot be edited. Restore it first.")

    if "fen" in changes or "solution" in changes:
        fen = changes.get("fen") or puzzle.fen
        solution = changes.get("solution") or puzzle.solution
        fen, solution = _check_position(fen, solution)

        if (fen, solution) != (puzzle.fen, puzzle.solution):
            assignment_count, attempt_count = _usage_counts(db, puzzle.id)

            if assignment_count or attempt_count:
                raise ConflictError(
                    "The position and solution are locked because this puzzle is "
                    "used in assignments or has attempts."
                )

        puzzle.fen, puzzle.solution = fen, solution

    if "category_id" in changes:
        _check_category(db, changes["category_id"])
        puzzle.category_id = changes["category_id"]

    for field in ("rating", "difficulty", "explanation"):
        if field in changes:
            setattr(puzzle, field, changes[field])

    if changes.get("type"):
        puzzle.type = changes["type"]

    if changes.get("theme_ids") is not None:
        _set_themes(db, puzzle, changes["theme_ids"])

    db.commit()
    db.refresh(puzzle)

    return puzzle_detail(db, trainer, puzzle)


PUZZLE_TRANSITIONS = {
    # action: (allowed current statuses, new status)
    "publish": ({"draft", "archived"}, "published"),
    "unpublish": ({"published"}, "draft"),
    "archive": ({"draft", "published"}, "archived"),
    "restore": ({"archived"}, "draft"),
}


def change_puzzle_status(db: Session, trainer: TrainerProfile, puzzle_id: uuid.UUID, action: str) -> dict:
    puzzle = get_owned_puzzle(db, trainer, puzzle_id)
    allowed, new_status = PUZZLE_TRANSITIONS[action]

    if puzzle.status not in allowed:
        raise ConflictError(f"Cannot {action} a puzzle that is {puzzle.status}.")

    if new_status == "published":
        # Re-check in case validation rules tightened since it was saved.
        _check_position(puzzle.fen, puzzle.solution)

    puzzle.status = new_status
    db.commit()
    db.refresh(puzzle)

    return puzzle_detail(db, trainer, puzzle)
