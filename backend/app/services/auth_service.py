
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_purpose_token,
    decode_purpose_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


REFRESH_TOKEN_EXPIRE_DAYS = 7

# Accounts created by scripts/seed.py, offered for one-click demo sign-in
# when settings.demo_login_enabled is on.
DEMO_ACCOUNT_EMAILS = {
    "admin": "admin@chessacademy.local",
    "trainer": "trainer@chessacademy.local",
    "student": "student1@chessacademy.local",
}

EMAIL_VERIFICATION_TOKEN_TYPE = "email_verification"
PASSWORD_RESET_TOKEN_TYPE = "password_reset"

# Verified against when the email is unknown, so failed logins take the
# same time whether or not the account exists.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


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
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return user


def get_demo_accounts(db: Session) -> list[User]:
    """Return the seeded demo accounts that exist, are active and match their role."""

    users = db.scalars(
        select(User).where(User.email.in_(DEMO_ACCOUNT_EMAILS.values()))
    )

    return sorted(
        (
            user
            for user in users
            if user.is_active and DEMO_ACCOUNT_EMAILS.get(user.role) == user.email
        ),
        key=lambda user: list(DEMO_ACCOUNT_EMAILS).index(user.role),
    )


def get_demo_user(db: Session, role: str) -> User | None:
    """Return the active demo account for ``role``, if it has been seeded."""

    user = db.scalar(
        select(User).where(User.email == DEMO_ACCOUNT_EMAILS.get(role))
    )

    if user is None or not user.is_active or user.role != role:
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

        if stored_token.is_revoked or stored_token.revoked_at is not None:
            # A revoked token was replayed: assume it was stolen and
            # revoke every active refresh token for this user.
            revoke_all_refresh_tokens(db, stored_token.user_id, now)
            db.commit()
            return None

        expires_at = stored_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
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


def revoke_all_refresh_tokens(
    db: Session,
    user_id: uuid.UUID,
    now: datetime,
) -> None:
    """Revoke every active refresh token of a user (caller commits)."""

    active_tokens = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked.is_(False),
        )
    )

    for token in active_tokens:
        token.is_revoked = True
        token.revoked_at = now


def _password_fingerprint(password_hash: str) -> str:
    # Changes whenever the password changes, which makes reset tokens
    # single-use without storing them.
    return hashlib.sha256(password_hash.encode()).hexdigest()[:32]


def _get_user_from_token(
    db: Session,
    token: str,
    token_type: str,
) -> tuple[User, dict] | None:
    payload = decode_purpose_token(token, token_type)

    if payload is None:
        return None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        return None

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        return None

    return user, payload


def create_email_verification_token(
    user: User,
    expires_delta: timedelta | None = None,
) -> str:
    return create_purpose_token(
        str(user.id),
        EMAIL_VERIFICATION_TOKEN_TYPE,
        expires_delta
        or timedelta(minutes=settings.email_verification_token_expire_minutes),
        {"email": user.email},
    )


def verify_email(db: Session, token: str) -> bool:
    """Mark the user's email as verified. Each token works only once."""

    result = _get_user_from_token(db, token, EMAIL_VERIFICATION_TOKEN_TYPE)

    if result is None:
        return False

    user, payload = result

    if user.is_verified or payload.get("email") != user.email:
        return False

    user.is_verified = True
    db.commit()

    return True


def create_password_reset_token(
    user: User,
    expires_delta: timedelta | None = None,
) -> str:
    return create_purpose_token(
        str(user.id),
        PASSWORD_RESET_TOKEN_TYPE,
        expires_delta
        or timedelta(minutes=settings.password_reset_token_expire_minutes),
        {"pwd": _password_fingerprint(user.password_hash)},
    )


def request_password_reset(
    db: Session,
    email: str,
) -> tuple[User, str] | None:
    """Return the user and a reset token, or None if no active account."""

    user = db.scalar(
        select(User).where(User.email == email.strip().lower())
    )

    if user is None or not user.is_active:
        return None

    return user, create_password_reset_token(user)


def reset_password(
    db: Session,
    token: str,
    new_password: str,
) -> bool:
    """Set a new password and revoke all of the user's refresh tokens."""

    result = _get_user_from_token(db, token, PASSWORD_RESET_TOKEN_TYPE)

    if result is None:
        return False

    user, payload = result

    if not secrets.compare_digest(
        str(payload.get("pwd", "")),
        _password_fingerprint(user.password_hash),
    ):
        return False

    user.password_hash = hash_password(new_password)
    revoke_all_refresh_tokens(db, user.id, datetime.now(timezone.utc))
    db.commit()

    return True
