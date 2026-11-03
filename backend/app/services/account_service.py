"""Account settings shared by every role: language, notification and board
preferences, and changing the password while signed in.

Preferences live in ``users.settings`` (JSONB). Only the keys defined here
are ever written, so the column cannot be used to store arbitrary data.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import ValidationError
from app.core.security import hash_password, verify_password
from app.models import User
from app.services import notification_service
from app.services.auth_service import revoke_all_refresh_tokens

BOARD_THEMES = ("wood", "green", "blue", "slate")
PIECE_SETS = ("classic", "glyph")
LANGUAGES = ("en", "hi", "ta", "te", "kn", "ml", "fr", "es", "de")

BOARD_DEFAULTS = {"theme": "wood", "pieces": "classic", "show_coordinates": True}


def board_preferences(user: User) -> dict:
    stored = (user.settings or {}).get("board") or {}
    prefs = dict(BOARD_DEFAULTS)

    if stored.get("theme") in BOARD_THEMES:
        prefs["theme"] = stored["theme"]
    if stored.get("pieces") in PIECE_SETS:
        prefs["pieces"] = stored["pieces"]
    if isinstance(stored.get("show_coordinates"), bool):
        prefs["show_coordinates"] = stored["show_coordinates"]

    return prefs


def get_settings(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "phone": user.phone,
        "language": user.language,
        "notifications": notification_service.preferences(user),
        "board": board_preferences(user),
        "options": {
            "languages": list(LANGUAGES),
            "board_themes": list(BOARD_THEMES),
            "piece_sets": list(PIECE_SETS),
        },
    }


def update_settings(db: Session, user: User, changes: dict) -> dict:
    """Apply a partial update; nested preference objects merge key by key."""
    settings = dict(user.settings or {})

    if "full_name" in changes:
        user.full_name = changes["full_name"]
    if "phone" in changes:
        user.phone = changes["phone"]
    if "language" in changes:
        user.language = changes["language"]

    for key, current in (
        ("notifications", notification_service.preferences(user)),
        ("board", board_preferences(user)),
    ):
        if changes.get(key):
            current.update({name: value for name, value in changes[key].items() if value is not None})
            settings[key] = current

    user.settings = settings
    flag_modified(user, "settings")
    db.commit()
    db.refresh(user)
    return get_settings(user)


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    """Change the password and sign out every other session."""
    if not verify_password(current_password, user.password_hash):
        raise ValidationError("Your current password is incorrect.")

    if verify_password(new_password, user.password_hash):
        raise ValidationError("Choose a password different from your current one.")

    user.password_hash = hash_password(new_password)
    revoke_all_refresh_tokens(db, user.id, datetime.now(timezone.utc))
    db.commit()
