
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


REFRESH_TOKEN_EXPIRE_DAYS = 7


def register_user(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    role: str = "student",
) -> User:
    """Create a new user account."""

    email = email.strip().lower()

    if role not in {"admin", "trainer", "student"}:
        raise ValueError("Invalid user role.")

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise ValueError("Email is already registered.")

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    """Verify login credentials."""

    email = email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return user


def create_refresh_token(
    db: Session,
    user_id: uuid.UUID,
) -> str:
    """Create a refresh token and store only its hash."""

    raw_token = secrets.token_urlsafe(48)
    token_jti = str(uuid.uuid4())

    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    refresh_token = RefreshToken(
        user_id=user_id,
        token_jti=token_jti,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    db.add(refresh_token)
    db.commit()

    return f"{token_jti}.{raw_token}"


def issue_tokens(
    db: Session,
    user: User,
) -> dict:
    """Issue an access token and a refresh token."""

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
def rotate_refresh_token(
    db: Session,
    submitted_token: str,
) -> dict | None:
    """Validate and rotate a refresh token."""

    try:
        token_jti, raw_token = submitted_token.split(".", 1)
        uuid.UUID(token_jti)
    except (ValueError, AttributeError):
        return None

    try:
        stored_token = db.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_jti == token_jti)
            .with_for_update()
        )

        if stored_token is None:
            db.rollback()
            return None

        submitted_hash = hashlib.sha256(
            raw_token.encode()
        ).hexdigest()

        if not secrets.compare_digest(
            submitted_hash,
            stored_token.token_hash,
        ):
            db.rollback()
            return None

        now = datetime.now(timezone.utc)

        expires_at = stored_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if (
            stored_token.is_revoked
            or stored_token.revoked_at is not None
            or expires_at <= now
        ):
            db.rollback()
            return None

        user = db.get(User, stored_token.user_id)

        if user is None or not user.is_active:
            db.rollback()
            return None

        # Revoke the old token.
        stored_token.is_revoked = True
        stored_token.revoked_at = now

        # Create a replacement token.
        new_raw_token = secrets.token_urlsafe(48)
        new_jti = str(uuid.uuid4())

        new_hash = hashlib.sha256(
            new_raw_token.encode()
        ).hexdigest()

        new_token = RefreshToken(
            user_id=user.id,
            token_jti=new_jti,
            token_hash=new_hash,
            expires_at=now + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS
            ),
        )

        db.add(new_token)
        db.commit()

        return {
            "access_token": create_access_token(str(user.id)),
            "refresh_token": f"{new_jti}.{new_raw_token}",
            "token_type": "bearer",
        }

    except SQLAlchemyError:
        db.rollback()
        raise

def revoke_refresh_token(
    db: Session,
    submitted_token: str,
    user_id: uuid.UUID,
) -> bool:
    """Revoke a user's refresh token during logout."""

    try:
        token_jti, raw_token = submitted_token.split(".", 1)
        uuid.UUID(token_jti)
    except (ValueError, AttributeError):
        return False

    stored_token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_jti == token_jti,
            RefreshToken.user_id == user_id,
        )
    )

    if stored_token is None:
        return False

    submitted_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    if not secrets.compare_digest(
        submitted_hash,
        stored_token.token_hash,
    ):
        return False

    now = datetime.now(timezone.utc)

    stored_token.is_revoked = True
    stored_token.revoked_at = now

    db.commit()

    return True
