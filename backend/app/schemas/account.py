import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import validate_password_strength
from app.services.account_service import BOARD_THEMES, LANGUAGES, PIECE_SETS
from app.utils.pagination import Page

BoardTheme = Literal[BOARD_THEMES]  # type: ignore[valid-type]
PieceSet = Literal[PIECE_SETS]  # type: ignore[valid-type]
Language = Literal[LANGUAGES]  # type: ignore[valid-type]


class NotificationPreferences(BaseModel):
    sessions: bool
    assignments: bool
    feedback: bool
    content: bool
    email: bool


class NotificationPreferencesUpdate(BaseModel):
    sessions: bool | None = None
    assignments: bool | None = None
    feedback: bool | None = None
    content: bool | None = None
    email: bool | None = None

    model_config = ConfigDict(extra="forbid")


class BoardPreferences(BaseModel):
    theme: str
    pieces: str
    show_coordinates: bool


class BoardPreferencesUpdate(BaseModel):
    theme: BoardTheme | None = None
    pieces: PieceSet | None = None
    show_coordinates: bool | None = None

    model_config = ConfigDict(extra="forbid")


class SettingsOptions(BaseModel):
    languages: list[str]
    board_themes: list[str]
    piece_sets: list[str]


class AccountSettings(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    phone: str | None = None
    language: str
    notifications: NotificationPreferences
    board: BoardPreferences
    options: SettingsOptions


class AccountSettingsUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    language: Language | None = None
    notifications: NotificationPreferencesUpdate | None = None
    board: BoardPreferencesUpdate | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value):
        if value is None:
            raise ValueError("Name cannot be empty.")
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters.")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")

    check_password = field_validator("new_password")(validate_password_strength)


class NotificationItem(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    notification_type: str
    is_read: bool
    read_at: datetime | None = None
    data: dict
    created_at: datetime


class NotificationPage(Page[NotificationItem]):
    unread: int


class UnreadCount(BaseModel):
    unread: int


class MarkedCount(BaseModel):
    marked: int
