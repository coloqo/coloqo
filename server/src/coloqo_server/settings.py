"""Instance settings, read from the environment."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BUNDLED_WEB_DIR = Path(__file__).parent / "static"
"""Where a release wheel carries the built web interface (decision 0016)."""


def bundled_web_dir() -> Path | None:
    """Return the web interface bundled into the installed package, if it is there.

    A release wheel carries it; a development checkout does not, and Vite serves the web.
    """
    return BUNDLED_WEB_DIR if (BUNDLED_WEB_DIR / "index.html").is_file() else None


class Settings(BaseSettings):
    """Settings of one Coloqo instance.

    Every field is read from an environment variable with the ``COLOQO_`` prefix,
    e.g. ``COLOQO_WEB_DIR``.

    Attributes:
        web_dir: Directory with the built web interface, served at ``/`` next to the API
            (decision 0010). Defaults to the one bundled into a release wheel; ``None``
            serves only the API, as in development, where Vite serves the web.
        host: Interface to listen on. The cloud instance listens on ``127.0.0.1`` behind
            Caddy; a container listens on all interfaces.
        port: Port to listen on.
        database_url: SQLAlchemy URL of the PostgreSQL database (decision 0008).
        public_url: The address people open; the origin that state-changing requests
            from the web must come from, and the base of links the server hands out.
        github_client_id: Client ID of the GitHub OAuth App; without it GitHub login is off.
        github_client_secret: Client secret of the GitHub OAuth App.
        dev_login: Allow logging in by name without a provider. For development and tests
            only: anyone can log in as anyone.
        files_dir: Where uploaded files are kept (decision 0008).
        max_file_bytes: Largest file a Topic accepts.
        team_storage_bytes: Total size of files a Team can keep.
        preview_max_bytes: Largest image the web shows inline; a larger one is listed as an
            ordinary file, since there are no thumbnails yet (decision 0018).
        event_retention_days: How long the event log is kept (decision 0008).
    """

    model_config = SettingsConfigDict(env_prefix="COLOQO_")

    web_dir: Path | None = Field(default_factory=bundled_web_dir)
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+psycopg://coloqo:dev@127.0.0.1:55432/coloqo"
    public_url: str = "http://localhost:5173"
    github_client_id: str | None = None
    github_client_secret: str | None = None
    dev_login: bool = False
    files_dir: Path = Path("var/files")
    max_file_bytes: int = 100 * 1024 * 1024
    team_storage_bytes: int = 5 * 1024 * 1024 * 1024
    preview_max_bytes: int = 10 * 1024 * 1024
    event_retention_days: int = 7
