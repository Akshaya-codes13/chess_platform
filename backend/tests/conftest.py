import secrets

import pytest

from app.core.database import SessionLocal
from app.core.security import hash_password
from scripts import seed


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
