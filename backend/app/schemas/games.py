import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.utils.pagination import Page


class GameDatabaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    is_shared: bool = False


class GameDatabaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    is_shared: bool | None = None


class GameDatabaseItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_shared: bool
    owner_id: uuid.UUID
    owner_name: str
    game_count: int
    can_edit: bool
    created_at: datetime


class FolderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    parent_id: uuid.UUID | None = None


class FolderRename(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)


class FolderItem(BaseModel):
    id: uuid.UUID
    name: str
    game_count: int


class FolderRef(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None


class Breadcrumb(BaseModel):
    # None is the database root.
    id: uuid.UUID | None
    name: str


class GameSummary(BaseModel):
    id: uuid.UUID
    database_id: uuid.UUID
    folder_id: uuid.UUID | None
    white: str
    black: str
    result: str
    event: str | None
    game_date: str | None
    eco: str | None
    white_elo: int | None
    black_elo: int | None
    ply_count: int
    created_at: datetime


class BrowseResponse(BaseModel):
    database: GameDatabaseItem
    folder: FolderRef | None
    breadcrumbs: list[Breadcrumb]
    folders: list[FolderItem]
    games: Page[GameSummary]


class ImportIssue(BaseModel):
    index: int
    error: str


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[ImportIssue]
    games: list[GameSummary]


class GamePosition(BaseModel):
    ply: int
    san: str | None
    uci: str | None
    fen: str


class GameDetail(GameSummary):
    site: str | None
    round: str | None
    initial_fen: str
    headers: dict[str, str]
    moves: list[str]
    positions: list[GamePosition]
    pgn: str
    can_edit: bool
    breadcrumbs: list[Breadcrumb]


class GameMove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None moves the game to the database root.
    folder_id: uuid.UUID | None
