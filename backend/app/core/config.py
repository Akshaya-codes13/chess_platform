
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    cors_origins: str = "http://localhost:5173"

    # Per-client limit for sensitive authentication endpoints.
    auth_rate_limit_enabled: bool = True
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 60

    email_verification_token_expire_minutes: int = 1440
    password_reset_token_expire_minutes: int = 30

    # One-click sign-in to the seeded demo accounts. Development only.
    demo_login_enabled: bool = False
    chess_seed_password: str | None = None

    # Object storage for uploaded images. "local" keeps files under
    # media_root (a Docker volume); other backends plug in via
    # app.services.storage.
    storage_backend: str = "local"
    media_root: str = "/data/media"
    media_max_bytes: int = 5 * 1024 * 1024
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
