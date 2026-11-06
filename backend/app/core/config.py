import logging
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Production secrets must be at least this long (HS256 wants >= 256 bits).
MIN_SECRET_KEY_LENGTH = 32

# Fragments of well-known placeholder values (compared case-insensitively),
# including the one shipped in backend/.env.example.
PLACEHOLDER_SECRET_FRAGMENTS = (
    "change-me",
    "changeme",
    "change_me",
    "your-secret",
    "your_secret",
    "secret-key",
    "secret_key",
    "not-for-production",
    "placeholder",
    "example",
)

GENERATE_SECRET_HINT = (
    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
)


def secret_key_problems(secret: str) -> list[str]:
    """Reasons ``secret`` is unfit for production (an empty list if it is fine)."""
    problems = []
    if len(secret) < MIN_SECRET_KEY_LENGTH:
        problems.append(f"it is shorter than {MIN_SECRET_KEY_LENGTH} characters")
    lowered = secret.lower()
    if any(fragment in lowered for fragment in PLACEHOLDER_SECRET_FRAGMENTS):
        problems.append("it looks like a placeholder value")
    if len(set(secret)) < 10:
        problems.append("it uses too few distinct characters")
    return problems


class Settings(BaseSettings):
    # "production" enforces a strong SECRET_KEY. "development" (the default)
    # and "test" accept any non-empty key and only log a warning.
    app_env: Literal["development", "test", "production"] = "development"

    database_url: str
    redis_url: str
    secret_key: str
    cors_origins: str = "http://localhost:5173"

    # SQLAlchemy connection pool (per process). The backend runs sync
    # endpoints on a threadpool of ~40 threads, so pool_size + max_overflow
    # bounds how many of them can hold a connection at once. Keep the total
    # across all processes below PostgreSQL's max_connections (100 by default).
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)
    db_pool_timeout_seconds: int = Field(default=30, ge=1)
    # Recycle connections older than this (seconds); -1 disables recycling.
    db_pool_recycle_seconds: int = Field(default=1800, ge=-1)
    # PostgreSQL statement_timeout for application connections, in
    # milliseconds; 0 disables it. Alembic migrations use their own engine
    # and are not affected.
    db_statement_timeout_ms: int = Field(default=30_000, ge=0)

    # Per-client limit for sensitive authentication endpoints.
    auth_rate_limit_enabled: bool = True
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 60

    email_verification_token_expire_minutes: int = 1440
    password_reset_token_expire_minutes: int = 30

    # One-click sign-in to the seeded demo accounts. Development only:
    # rejected at startup when APP_ENV=production.
    demo_login_enabled: bool = False
    chess_seed_password: str | None = None

    # Object storage for uploaded images. "local" keeps files under
    # media_root (a Docker volume); other backends plug in via
    # app.services.storage.
    storage_backend: str = "local"
    media_root: str = "/data/media"
    media_max_bytes: int = 5 * 1024 * 1024
    # hide_input_in_errors keeps SECRET_KEY and DATABASE_URL (with its
    # password) out of validation error messages and startup tracebacks.
    model_config = SettingsConfigDict(env_file=".env", hide_input_in_errors=True)

    @model_validator(mode="after")
    def _check_demo_login(self) -> "Settings":
        # Demo login signs in to seeded accounts without a password.
        if self.demo_login_enabled and self.app_env == "production":
            raise ValueError(
                "DEMO_LOGIN_ENABLED must be false when APP_ENV=production: "
                "demo login signs in without a password."
            )
        return self

    @model_validator(mode="after")
    def _check_secret_key(self) -> "Settings":
        # The key is never included in messages.
        if not self.secret_key.strip():
            raise ValueError(f"SECRET_KEY must not be empty. {GENERATE_SECRET_HINT}")

        problems = secret_key_problems(self.secret_key)
        if problems and self.app_env == "production":
            raise ValueError(
                "SECRET_KEY is not safe for production: "
                + "; ".join(problems)
                + f". {GENERATE_SECRET_HINT}"
            )
        if problems:
            logger.warning(
                "SECRET_KEY is weak (%s). This is accepted because APP_ENV=%s, "
                "but it would be rejected with APP_ENV=production.",
                "; ".join(problems),
                self.app_env,
            )
        return self


settings = Settings()
