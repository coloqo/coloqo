"""Instance settings, read from the environment."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings of one Coloqo instance.

    Every field is read from an environment variable with the ``COLOQO_`` prefix,
    e.g. ``COLOQO_WEB_DIR``.

    Attributes:
        web_dir: Directory with the built web interface. When set, the server serves it
            at ``/`` next to the API (decision 0010); when empty, only the API is served,
            as in development, where Vite serves the web.
    """

    model_config = SettingsConfigDict(env_prefix="COLOQO_")

    web_dir: Path | None = None
