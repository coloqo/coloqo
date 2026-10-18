"""Alembic environment: migrations run synchronously over psycopg."""

from alembic import context
from sqlalchemy import create_engine

from coloqo_server.models import Base

config = context.config


def run() -> None:
    """Apply the migrations on a connection to the configured database.

    Raises:
        sqlalchemy.exc.OperationalError: The database cannot be reached.
    """
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run()
