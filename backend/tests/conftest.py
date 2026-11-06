"""Shared test fixtures.

Isolation from the development data
-----------------------------------
Tests never touch the development database or Redis DB:

* The database URL is switched to ``TEST_DATABASE_URL`` or, by default, to
  ``DATABASE_URL`` with ``_test`` appended to the database name
  (``chess_academy`` -> ``chess_academy_test``). The run aborts if the
  resulting database name does not end in ``_test``.
* Redis is switched to ``TEST_REDIS_URL`` or, by default, DB index 15 on the
  ``REDIS_URL`` server (rate-limit counters, streak cache, ARQ job queue).
* The test database is created if missing and upgraded to the Alembic head
  once per test run (``_test_database``).
* Every test runs inside one outer transaction on one connection that is
  rolled back afterwards (``_isolated_transaction``). ``SessionLocal`` (and
  so the API's ``get_db``) is bound to that connection in savepoint mode,
  so ``commit()`` inside services only releases a savepoint and nothing
  persists between tests.

The URL switch must happen before ``app.core.database`` is imported, because
the engine is created at import time. Keep it at the top of this module.
"""

import os
import secrets
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from sqlalchemy.engine import make_url

from app.core.config import settings

TEST_DB_SUFFIX = "_test"
TEST_REDIS_DB = 15
BACKEND_DIR = Path(__file__).resolve().parent.parent


def derive_test_database_url(database_url: str, explicit: str | None = None):
    """The URL tests use: ``explicit`` if given, else ``<name>_test``."""
    url = make_url(explicit or database_url)
    if not explicit and not (url.database or "").endswith(TEST_DB_SUFFIX):
        url = url.set(database=f"{url.database}{TEST_DB_SUFFIX}")
    return url


def derive_test_redis_url(redis_url: str, explicit: str | None = None) -> str:
    """The Redis URL tests use: ``explicit`` if given, else DB index 15."""
    if explicit:
        return explicit
    parts = urlsplit(redis_url)
    return urlunsplit(parts._replace(path=f"/{TEST_REDIS_DB}"))


_TEST_DB_URL = derive_test_database_url(settings.database_url, os.environ.get("TEST_DATABASE_URL"))

if not (_TEST_DB_URL.database or "").endswith(TEST_DB_SUFFIX):
    pytest.exit(
        f"Refusing to run tests against database {_TEST_DB_URL.database!r}: "
        f"the test database name must end with {TEST_DB_SUFFIX!r}.",
        returncode=2,
    )

settings.database_url = _TEST_DB_URL.render_as_string(hide_password=False)
settings.redis_url = derive_test_redis_url(settings.redis_url, os.environ.get("TEST_REDIS_URL"))

# Everything below may import app.core.database.
import redis  # noqa: E402
from alembic import command as alembic_command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, text  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.rate_limit import rate_limit_key, redis_client  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.services.auth_service import register_user  # noqa: E402
from scripts import seed  # noqa: E402

TEST_CLIENT_HOST = "testclient"

assert engine.url.database.endswith(TEST_DB_SUFFIX), "engine was created before the test URL switch"


def _ensure_test_database(url) -> None:
    """Create the test database if it does not exist (never drops anything)."""
    maintenance = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with maintenance.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                # The name is validated above (suffix check) and quoted here.
                quoted = maintenance.dialect.identifier_preparer.quote(url.database)
                connection.execute(text(f"CREATE DATABASE {quoted}"))
    finally:
        maintenance.dispose()


def _upgrade_test_database() -> None:
    # A Config without an ini file skips alembic's logging setup, which would
    # otherwise disable the application's loggers for the rest of the run.
    config = AlembicConfig()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Create (if needed) and migrate the test database once per run."""
    _ensure_test_database(engine.url)
    _upgrade_test_database()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _isolated_transaction(_test_database, monkeypatch):
    """Run the test inside one transaction that is always rolled back.

    Every ``SessionLocal()`` (the API's ``get_db``, fixtures, services and
    tests) joins this connection in savepoint mode, so their ``commit()``
    calls release savepoints instead of committing.
    """
    connection = engine.connect()
    transaction = connection.begin()
    monkeypatch.setitem(SessionLocal.kw, "bind", connection)
    monkeypatch.setitem(SessionLocal.kw, "join_transaction_mode", "create_savepoint")
    try:
        yield connection
    finally:
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def db():
    """Database session whose changes are rolled back after each test."""
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def seeded_db(db):
    """Session with the demo data seeded inside the test transaction.

    Existing records are preserved by the seed functions, and anything they
    create is discarded by the rollback in the ``db`` fixture.
    """
    seed.seed_all(db, hash_password(secrets.token_urlsafe(16)))
    return db


def clear_test_rate_limits():
    try:
        for key in redis_client.scan_iter(rate_limit_key("*", TEST_CLIENT_HOST)):
            redis_client.delete(key)
    except redis.RedisError:
        pass


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Start every test with empty rate-limit counters for the test client."""
    clear_test_rate_limits()
    yield
    clear_test_rate_limits()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def created_emails():
    """Emails of users created by a test; those users are deleted afterwards."""
    emails = []
    yield emails

    if emails:
        session = SessionLocal()
        try:
            session.execute(delete(User).where(User.email.in_(emails)))
            session.commit()
        finally:
            session.close()


@pytest.fixture()
def unique_email(created_emails):
    email = f"test-{uuid.uuid4().hex}@example.com"
    created_emails.append(email)
    return email


def make_password():
    return f"Pw1{secrets.token_urlsafe(12)}"


@pytest.fixture()
def create_user(created_emails):
    """Create a throwaway user and return ``(user, password)``."""

    def factory(role="student"):
        email = f"test-{uuid.uuid4().hex}@example.com"
        created_emails.append(email)
        password = make_password()

        session = SessionLocal()
        try:
            user = register_user(
                session,
                email=email,
                password=password,
                full_name="Test User",
                role=role,
            )
            session.expunge(user)
        finally:
            session.close()

        return user, password

    return factory


def auth_headers(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
