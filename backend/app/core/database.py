from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


# Consistent names for database constraints and indexes
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def engine_options(config=settings) -> dict:
    """Pool and connection options for the application engine."""
    options = {
        "pool_pre_ping": True,
        "pool_size": config.db_pool_size,
        "max_overflow": config.db_max_overflow,
        "pool_timeout": config.db_pool_timeout_seconds,
        "pool_recycle": config.db_pool_recycle_seconds,
    }
    if config.db_statement_timeout_ms > 0 and make_url(config.database_url).get_backend_name() == "postgresql":
        # Abort any single statement that runs longer than this, so a runaway
        # query cannot hold a pooled connection (and its locks) indefinitely.
        options["connect_args"] = {
            "options": f"-c statement_timeout={config.db_statement_timeout_ms}"
        }
    return options


engine = create_engine(settings.database_url, **engine_options())

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()