from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine, Session
from bangstats_server.core.config import DB_PATH

# Database configuration
# Database URL
SQLITE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(SQLITE_URL, echo=False)


def init_db():
    """Initialize the database by creating all tables."""
    SQLModel.metadata.create_all(engine)
    _run_schema_migrations()


def _run_schema_migrations():
    """
    Apply lightweight, idempotent schema migrations.

    SQLModel `create_all` only creates missing tables and does not alter existing ones.
    This keeps existing local SQLite databases compatible after model changes.
    """
    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())

        if "screenshot" in table_names:
            existing_columns = {column["name"] for column in inspector.get_columns("screenshot")}
            if "filename" not in existing_columns:
                connection.execute(text("ALTER TABLE screenshot ADD COLUMN filename VARCHAR"))


def get_session():
    """Get a new database session."""
    with Session(engine) as session:
        yield session


# Make sure to import your models here to register them with SQLModel
from bangstats_server.core.db.models.song import Song # noqa
from bangstats_server.core.db.models.event import Event # noqa
from bangstats_server.core.db.models.band import Band # noqa
from bangstats_server.core.db.models.screenshot import Screenshot # noqa
from bangstats_server.core.db.models.sync_job import SyncJob # noqa
from bangstats_server.core.db.models.user import User # noqa
