from threading import Lock

from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine, Session
from bangstats_server.core.config import DB_PATH

# Database configuration
# Database URL
SQLITE_URL = f"sqlite:///{DB_PATH}"

_engine_lock = Lock()


def _create_db_engine():
    return create_engine(SQLITE_URL, echo=False)


# Create engine
engine = _create_db_engine()


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

        if "user" in table_names:
            existing_columns = {column["name"] for column in inspector.get_columns("user")}
            if "password_hash" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE user ADD COLUMN password_hash VARCHAR DEFAULT ''")
                )
            if "server_folder_authorized" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE user ADD COLUMN server_folder_authorized BOOLEAN DEFAULT 0")
                )
            if "sync_command" not in existing_columns:
                connection.execute(
                    text("ALTER TABLE user ADD COLUMN sync_command VARCHAR")
                )


def get_session():
    """Get a new database session."""
    with Session(engine) as session:
        yield session


def reset_db_engine():
    """Dispose and recreate DB engine after DB file moves."""
    global engine
    with _engine_lock:
        try:
            engine.dispose()
        except Exception:
            pass
        engine = _create_db_engine()
        init_db()


# Make sure to import your models here to register them with SQLModel
from bangstats_server.core.db.models.song import Song # noqa
from bangstats_server.core.db.models.event import Event # noqa
from bangstats_server.core.db.models.band import Band # noqa
from bangstats_server.core.db.models.screenshot import Screenshot # noqa
from bangstats_server.core.db.models.scan_job import ScanJob # noqa
from bangstats_server.core.db.models.sync_job import SyncJob # noqa
from bangstats_server.core.db.models.user import User # noqa
from bangstats_server.core.db.models.token import Token # noqa
