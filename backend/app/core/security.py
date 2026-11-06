from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext

from app.core.config import settings

ACCESS_TOKEN_EXPIRE_MINUTES = 30
ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    """Verify and decode an access token."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )

        if payload.get("type") != "access":
            return None

        return payload

    except JWTError:
        return None


def create_purpose_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    claims: dict | None = None,
) -> str:
    """Create a signed, short-lived token for a single purpose.

    Used for email verification and password reset. The distinct ``type``
    claim stops these tokens from being accepted as access tokens.
    """
    now = datetime.now(timezone.utc)

    payload = {
        **(claims or {}),
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_purpose_token(token: str, token_type: str) -> dict | None:
    """Verify a purpose token's signature, expiry and type."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        return None

    if payload.get("type") != token_type or not payload.get("sub"):
        return None

    return payload

# Argon2 password hashing
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a password against its stored hash."""
    return pwd_context.verify(plain_password, hashed_password)
