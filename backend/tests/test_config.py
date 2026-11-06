"""Settings validation (SECRET_KEY, pool options) and test-database isolation."""

import logging
import os
import secrets
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text

from app.core.config import MIN_SECRET_KEY_LENGTH, Settings, secret_key_problems
from app.core.database import SessionLocal, engine, engine_options
from app.models import User
from tests.conftest import derive_test_database_url, derive_test_redis_url

STRONG_SECRET = secrets.token_urlsafe(48)
DB_URL = "postgresql+psycopg2://chess:pw@db:5432/chess_academy"


def make_settings(**overrides) -> Settings:
    values = {
        "database_url": DB_URL,
        "redis_url": "redis://redis:6379/0",
        "secret_key": STRONG_SECRET,
        "app_env": "production",
        # Pinned so a development .env (where demo login may be on) does not
        # leak into these production-mode checks.
        "demo_login_enabled": False,
    }
    values.update(overrides)
    # Init arguments take precedence over the environment; no .env is read.
    return Settings(_env_file=None, **values)


# SECRET_KEY validation


@pytest.mark.parametrize(
    "secret",
    [
        "change-me-in-production",  # the .env.example placeholder
        "CHANGE-ME-" + "x" * 40,  # placeholder, long enough
        "ci-test-secret-key-not-for-production",
        "short-but-random-Q9z!",  # too short
        "a" * 64,  # long, but a single repeated character
        "abababababababababababababababababab",
    ],
)
def test_production_rejects_weak_secret(secret):
    with pytest.raises(ValidationError) as exc_info:
        make_settings(secret_key=secret)

    message = str(exc_info.value)
    assert "SECRET_KEY is not safe for production" in message
    # Neither the rejected secret nor the database password is echoed back.
    assert secret not in message
    assert "pw@db" not in message


@pytest.mark.parametrize("env", ["production", "development", "test"])
@pytest.mark.parametrize("secret", ["", "   "])
def test_empty_secret_is_rejected_in_every_environment(env, secret):
    with pytest.raises(ValidationError, match="SECRET_KEY must not be empty"):
        make_settings(app_env=env, secret_key=secret)


def test_production_accepts_strong_secret():
    config = make_settings()
    assert config.app_env == "production"
    assert secret_key_problems(config.secret_key) == []


@pytest.mark.parametrize("env", ["development", "test"])
def test_non_production_accepts_weak_secret_with_warning(env, caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.config"):
        config = make_settings(app_env=env, secret_key="change-me-in-production")

    assert config.secret_key == "change-me-in-production"
    assert "SECRET_KEY is weak" in caplog.text
    assert "change-me-in-production" not in caplog.text


def test_default_environment_is_development():
    config = Settings(
        _env_file=None,
        database_url=DB_URL,
        redis_url="redis://redis:6379/0",
        secret_key=STRONG_SECRET,
    )
    # Only meaningful when APP_ENV is not set in the test environment.
    if config.app_env != "development":
        pytest.skip("APP_ENV is set in this environment")
    assert config.app_env == "development"


def test_unknown_environment_is_rejected():
    with pytest.raises(ValidationError):
        make_settings(app_env="prod")


def test_app_env_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_LOGIN_ENABLED", "false")
    with pytest.raises(ValidationError, match="not safe for production"):
        Settings(
            _env_file=None,
            database_url=DB_URL,
            redis_url="redis://redis:6379/0",
            secret_key="change-me-in-production",
        )


# Demo login (passwordless sign-in to the seeded accounts)


def test_production_rejects_demo_login():
    with pytest.raises(ValidationError, match="DEMO_LOGIN_ENABLED must be false when APP_ENV=production"):
        make_settings(demo_login_enabled=True)


def test_production_rejects_demo_login_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_LOGIN_ENABLED", "true")
    with pytest.raises(ValidationError, match="DEMO_LOGIN_ENABLED must be false"):
        Settings(
            _env_file=None,
            database_url=DB_URL,
            redis_url="redis://redis:6379/0",
            secret_key=STRONG_SECRET,
        )


def test_production_accepts_demo_login_disabled():
    assert make_settings(demo_login_enabled=False).demo_login_enabled is False


@pytest.mark.parametrize("env", ["development", "test"])
def test_non_production_allows_demo_login(env):
    assert make_settings(app_env=env, demo_login_enabled=True).demo_login_enabled is True


def test_secret_key_problems_lists_each_reason():
    problems = secret_key_problems("changeme")
    assert any("shorter than" in p for p in problems)
    assert any("placeholder" in p for p in problems)
    assert len(STRONG_SECRET) >= MIN_SECRET_KEY_LENGTH
    assert secret_key_problems(STRONG_SECRET) == []


# Connection pool options


def test_pool_settings_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "7")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "3")
    monkeypatch.setenv("DB_POOL_TIMEOUT_SECONDS", "11")
    monkeypatch.setenv("DB_POOL_RECYCLE_SECONDS", "600")
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "4500")
    config = make_settings()

    options = engine_options(config)

    assert options["pool_size"] == 7
    assert options["max_overflow"] == 3
    assert options["pool_timeout"] == 11
    assert options["pool_recycle"] == 600
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {"options": "-c statement_timeout=4500"}


def test_statement_timeout_zero_disables_it():
    options = engine_options(make_settings(db_statement_timeout_ms=0))
    assert "connect_args" not in options


@pytest.mark.parametrize(
    "field, value",
    [("db_pool_size", 0), ("db_max_overflow", -1), ("db_pool_timeout_seconds", 0), ("db_statement_timeout_ms", -5)],
)
def test_invalid_pool_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


def test_application_engine_uses_the_pool_settings():
    from app.core.config import settings

    assert engine.pool.size() == settings.db_pool_size
    if settings.db_statement_timeout_ms > 0:
        with engine.connect() as connection:
            timeout = connection.scalar(text("SHOW statement_timeout"))
        assert timeout != "0"


# Test-database isolation


def test_derived_test_urls():
    url = derive_test_database_url(DB_URL)
    assert url.database == "chess_academy_test"
    assert url.password == "pw"
    assert derive_test_database_url("postgresql://u@h/x_test").database == "x_test"
    assert derive_test_database_url(DB_URL, "postgresql://u@h/other_test").database == "other_test"

    assert derive_test_redis_url("redis://redis:6379/0") == "redis://redis:6379/15"
    assert derive_test_redis_url("redis://:pw@redis:6379") == "redis://:pw@redis:6379/15"
    assert derive_test_redis_url("redis://redis:6379/0", "redis://other:6379/3") == "redis://other:6379/3"


def test_tests_run_against_the_test_database():
    from app.core.config import settings

    assert engine.url.database.endswith("_test")
    assert settings.redis_url.endswith("/15") or "TEST_REDIS_URL" in os.environ
    with SessionLocal() as session:
        assert session.scalar(text("SELECT current_database()")).endswith("_test")


def test_service_commits_do_not_persist_outside_the_test():
    email = f"isolation-{uuid.uuid4().hex}@example.com"
    with SessionLocal() as session:
        session.add(User(email=email, password_hash="x", full_name="Isolation", role="student"))
        session.commit()

    # Visible inside the test's transaction...
    with SessionLocal() as session:
        assert session.scalar(select(User.id).where(User.email == email)) is not None

    # ...but not to any other connection, so nothing was really committed.
    with engine.connect() as other:
        assert other.scalar(select(User.id).where(User.email == email)) is None
