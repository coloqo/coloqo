"""Database access: the engine, sessions and migrations."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    """The engine of one database and a factory of its sessions."""

    def __init__(self, url: str) -> None:
        """Connect lazily to the database at ``url``.

        Args:
            url: SQLAlchemy URL with the ``postgresql+psycopg`` driver.

        Raises:
            sqlalchemy.exc.ArgumentError: The URL is malformed.
        """
        self.url = url
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        """Close all pooled connections."""
        await self.engine.dispose()


def migrate(url: str, files_dir: Path) -> None:
    """Bring the database schema to the newest migration.

    Runs at server start (decision 0013): one instance, so no other process races it.

    Args:
        url: SQLAlchemy URL of the database.
        files_dir: The instance's file directory, for migrations that read the files.

    Raises:
        sqlalchemy.exc.OperationalError: The database cannot be reached.
        alembic.util.exc.CommandError: The migrations are inconsistent.
    """
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["files_dir"] = Path(files_dir)
    command.upgrade(config, "head")
