import secrets
import uuid

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.core.rate_limit import rate_limit_key, redis_client
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import User
from app.services.auth_service import register_user
from scripts import seed

TEST_CLIENT_HOST = "testclient"


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
