"""The ASGI application."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import timedelta
from importlib.metadata import version

from fastapi import APIRouter, FastAPI
from sqlalchemy import delete

from coloqo_server import retention
from coloqo_server.api import auth, avatars, files, stream, teams, topics
from coloqo_server.db import Database, migrate
from coloqo_server.events import EventBus
from coloqo_server.models import DeviceLogin, Event, WebSession
from coloqo_server.providers import GitHub, LoginProvider
from coloqo_server.security import now
from coloqo_server.settings import Settings
from coloqo_server.web import SinglePageApp

log = logging.getLogger(__name__)

CLEANUP_SECONDS = 3600

api = APIRouter(prefix="/api")


@api.get("/health")
async def health() -> dict[str, str]:
    """Report that the server is up; the external monitor polls it (decision 0013)."""
    return {"status": "ok"}


for module in (auth, avatars, teams, topics, files, stream):
    api.include_router(module.router)


async def cleanup(database: Database, settings: Settings, bus: EventBus) -> None:
    """Drop old events, expired web sessions and plugin logins; tend Topics; once an hour.

    Topics: idle ones are warned and closed, archived ones lose their conversation (decision
    0021).

    Args:
        database: The database.
        settings: Instance settings with the event retention.
        bus: Wakes the streams of people told about Topics.
    """
    while True:
        try:
            async with database.sessions() as db:
                moment = now()
                await db.execute(
                    delete(Event).where(
                        Event.created_at < moment - timedelta(days=settings.event_retention_days)
                    )
                )
                await db.execute(delete(WebSession).where(WebSession.expires_at < moment))
                await db.execute(delete(DeviceLogin).where(DeviceLogin.expires_at < moment))
                await db.commit()
                bus.wake(await retention.tend(db, settings, moment))
        except Exception:
            log.exception("Cleanup failed")
        await asyncio.sleep(CLEANUP_SECONDS)


def create_app(
    settings: Settings | None = None, providers: dict[str, LoginProvider] | None = None
) -> FastAPI:
    """Build the application.

    Args:
        settings: Instance settings; read from the environment when omitted.
        providers: Login providers by name; built from the settings when omitted.

    Raises:
        pydantic.ValidationError: An environment variable holds an invalid value.
        RuntimeError: ``web_dir`` is set but the directory does not exist.
    """
    settings = settings or Settings()
    if providers is None:
        providers = {}
        if settings.github_client_id and settings.github_client_secret:
            providers["github"] = GitHub(settings.github_client_id, settings.github_client_secret)
    database = Database(settings.database_url)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Migrate the database, run the cleanup, close connections on shutdown.

        Args:
            app: The application.
        """
        await asyncio.to_thread(migrate, settings.database_url, settings.files_dir)
        task = asyncio.create_task(cleanup(database, settings, app.state.bus))
        yield
        task.cancel()
        await database.dispose()

    app = FastAPI(
        title="Coloqo",
        version=version("coloqo-server"),
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.bus = EventBus()
    app.state.providers = providers
    app.include_router(api)
    if settings.web_dir is not None:
        app.mount("/", SinglePageApp(directory=str(settings.web_dir)), name="web")
    return app
