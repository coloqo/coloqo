"""Run the server: ``python -m coloqo_server``."""

import uvicorn


def main() -> None:
    """Serve the application on port 8000 of all interfaces.

    Raises:
        pydantic.ValidationError: An environment variable holds an invalid value.
        RuntimeError: ``COLOQO_WEB_DIR`` is set but the directory does not exist.
        OSError: The port cannot be bound.
    """
    uvicorn.run(
        "coloqo_server.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
