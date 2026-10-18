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
    """

    model_config = SettingsConfigDict(env_prefix="COLOQO_")

    web_dir: Path | None = Field(default_factory=bundled_web_dir)
    host: str = "0.0.0.0"
    port: int = 8000
