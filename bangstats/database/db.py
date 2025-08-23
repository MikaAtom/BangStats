from sqlmodel import SQLModel, create_engine, Session
from bangstats.config.config import Config

# Database configuration
DB_PATH = Config.get("DB_PATH")


# Database URL
SQLITE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(SQLITE_URL, echo=False)


def init_db():
    """Initialize the database by creating all tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get a new database session."""
    with Session(engine) as session:
        yield session


# Make sure to import your models here to register them with SQLModel
from bangstats.database.models.song import Song # noqa
from bangstats.database.models.event import Event # noqa
from bangstats.database.models.band import Band # noqa
from bangstats.database.models.screenshot import Screenshot # noqa
from bangstats.database.models.user import User # noqa
