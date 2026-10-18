"""Run the server: ``python -m coloqo_server``."""

import uvicorn

from coloqo_server.settings import Settings


def main() -> None:
    """Serve the application on the configured interface and port.

    Raises:
        pydantic.ValidationError: An environment variable holds an invalid value.
        RuntimeError: ``COLOQO_WEB_DIR`` is set but the directory does not exist.
        OSError: The port cannot be bound.
    """
    settings = Settings()
    uvicorn.run(
        "coloqo_server.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
