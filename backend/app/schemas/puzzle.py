import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PuzzleDifficulty = Literal["beginner", "intermediate", "advanced"]
PuzzleType = Literal["puzzle", "study", "composition"]
PuzzleStatus = Literal["draft", "published", "archived"]

MAX_THEMES_PER_PUZZLE = 10


def reject_duplicate_ids(values: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
    if values is not None and len(set(values)) != len(values):
        raise ValueError("Duplicate ids are not allowed.")
    return values


class TaxonomyItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class TaxonomyResponse(BaseModel):
    categories: list[TaxonomyItem]
    themes: list[TaxonomyItem]


class PuzzleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fen: str = Field(min_length=1, max_length=100)
    solution: str = Field(min_length=1, max_length=400)
    rating: int | None = Field(default=None, ge=0, le=4000)
    difficulty: PuzzleDifficulty | None = None
    type: PuzzleType = "puzzle"
    category_id: uuid.UUID | None = None
    theme_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_THEMES_PER_PUZZLE)
    explanation: str | None = Field(default=None, max_length=5000)

    check_theme_ids = field_validator("theme_ids")(reject_duplicate_ids)


class PuzzleUpdate(BaseModel):
    """Partial update; only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    fen: str | None = Field(default=None, min_length=1, max_length=100)
    solution: str | None = Field(default=None, min_length=1, max_length=400)
    rating: int | None = Field(default=None, ge=0, le=4000)
    difficulty: PuzzleDifficulty | None = None
    type: PuzzleType | None = None
    category_id: uuid.UUID | None = None
    theme_ids: list[uuid.UUID] | None = Field(default=None, max_length=MAX_THEMES_PER_PUZZLE)
    explanation: str | None = Field(default=None, max_length=5000)

    check_theme_ids = field_validator("theme_ids")(reject_duplicate_ids)


class PuzzleValidateRequest(BaseModel):
    fen: str = Field(min_length=1, max_length=100)
    solution: str = Field(min_length=1, max_length=400)


class PuzzleValidateResponse(BaseModel):
    valid: bool
    error: str | None = None
    fen: str | None = None
    solution: str | None = None
    final_fen: str | None = None
    side_to_move: Literal["white", "black"] | None = None
    move_count: int | None = None
    ends_in_checkmate: bool | None = None


class PuzzleSummary(BaseModel):
    id: uuid.UUID
    fen: str
    rating: int | None
    difficulty: str | None
    type: str
    status: str
    source: str
    category: TaxonomyItem | None
    themes: list[TaxonomyItem]
    is_owner: bool
    created_at: datetime
    updated_at: datetime


class PuzzleDetail(PuzzleSummary):
    solution: str
    explanation: str | None
    side_to_move: Literal["white", "black"]
    assignment_count: int
    attempt_count: int
    # FEN and solution can no longer change once the puzzle is used by an
    # assignment or has attempts, so recorded results stay meaningful.
    solution_locked: bool
