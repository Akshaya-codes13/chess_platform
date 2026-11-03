"""PGN game library for every signed-in user; see game_library_service."""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import ValidationError
from app.models import User
from app.schemas.games import (
    BrowseResponse,
    FolderCreate,
    FolderItem,
    FolderRename,
    GameDatabaseCreate,
    GameDatabaseItem,
    GameDatabaseUpdate,
    GameDetail,
    GameMove,
    GameSummary,
    ImportResult,
)
from app.services import game_library_service as library
from app.utils.pagination import PageParams, page_params

router = APIRouter(prefix="/games", tags=["Game library"])


@router.get("/databases", response_model=list[GameDatabaseItem])
def list_databases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The caller's databases plus every shared database."""
    return library.list_databases(db, user)


@router.post("/databases", response_model=GameDatabaseItem, status_code=status.HTTP_201_CREATED)
def create_database(
    data: GameDatabaseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return library.create_database(db, user, data.model_dump())


@router.patch("/databases/{database_id}", response_model=GameDatabaseItem)
def update_database(
    database_id: uuid.UUID,
    data: GameDatabaseUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return library.update_database(db, user, database_id, data.model_dump(exclude_unset=True))


@router.delete("/databases/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_database(
    database_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Only databases without games can be deleted."""
    library.delete_database(db, user, database_id)


@router.get("/databases/{database_id}/browse", response_model=BrowseResponse)
def browse(
    database_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    search: str | None = Query(None, max_length=100),
    params: PageParams = Depends(page_params),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return library.browse(db, user, database_id, folder_id, search, params)


@router.post(
    "/databases/{database_id}/folders",
    response_model=FolderItem,
    status_code=status.HTTP_201_CREATED,
)
def create_folder(
    database_id: uuid.UUID,
    data: FolderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return library.create_folder(db, user, database_id, data.model_dump())


@router.patch("/folders/{folder_id}", response_model=FolderItem)
def rename_folder(
    folder_id: uuid.UUID,
    data: FolderRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return library.rename_folder(db, user, folder_id, data.name)


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Only empty folders can be deleted."""
    library.delete_folder(db, user, folder_id)


@router.post("/databases/{database_id}/import", response_model=ImportResult)
async def import_pgn(
    database_id: uuid.UUID,
    file: UploadFile | None = File(None),
    pgn: str | None = Form(None),
    folder_id: uuid.UUID | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import a .pgn file (``file``) or pasted PGN text (``pgn``)."""
    if file is not None:
        raw = await file.read(library.MAX_PGN_BYTES + 1)
    elif pgn is not None:
        raw = pgn.encode("utf-8")
    else:
        raise ValidationError("Upload a .pgn file or paste PGN text.")

    return library.import_pgn(db, user, database_id, folder_id, raw)


@router.get("/{game_id}", response_model=GameDetail)
def get_game(game_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return library.get_game(db, user, game_id)


@router.patch("/{game_id}", response_model=GameSummary)
def move_game(
    game_id: uuid.UUID,
    data: GameMove,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return library.move_game(db, user, game_id, data.folder_id)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(game_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    library.delete_game(db, user, game_id)
