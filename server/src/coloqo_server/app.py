"""The ASGI application."""

from fastapi import APIRouter, FastAPI

from coloqo_server.settings import Settings
from coloqo_server.web import SinglePageApp

api = APIRouter(prefix="/api")


@api.get("/health")
async def health() -> dict[str, str]:
    """Report that the server is up; the external monitor polls it (decision 0013)."""
    return {"status": "ok"}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Instance settings; read from the environment when omitted.

    Raises:
        pydantic.ValidationError: An environment variable holds an invalid value.
        RuntimeError: ``web_dir`` is set but the directory does not exist.
    """
    settings = settings or Settings()
    app = FastAPI(
        title="Coloqo",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.include_router(api)
    if settings.web_dir is not None:
        app.mount("/", SinglePageApp(directory=str(settings.web_dir)), name="web")
    return app
