"""The latest release of the plugin, learned from PyPI (decision 0027)."""

import asyncio
import logging

import httpx
from fastapi import FastAPI

from coloqo_server.security import plugin_version

log = logging.getLogger(__name__)

CHECK_SECONDS = 3600
"""How often the server asks PyPI."""


async def latest_release(url: str) -> tuple[int, ...] | None:
    """Return the latest version of the plugin on PyPI; ``None`` when it cannot be learned.

    Args:
        url: The package's JSON on PyPI.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            return plugin_version(response.json()["info"]["version"])
    except httpx.HTTPError, ValueError, KeyError, TypeError:
        return None


async def watch_releases(app: FastAPI, url: str) -> None:
    """Keep ``app.state.latest_plugin`` up to date, asking PyPI once an hour.

    A failed request keeps the last known version; without one, the briefing gives no hint.

    Args:
        app: The application.
        url: The package's JSON on PyPI.
    """
    while True:
        found = await latest_release(url)
        if found is not None:
            app.state.latest_plugin = found
        else:
            log.info("The latest plugin release is unknown: PyPI did not answer")
        await asyncio.sleep(CHECK_SECONDS)


def version_text(version: tuple[int, ...]) -> str:
    """Return a version as people write it.

    Args:
        version: The version's numbers.
    """
    return ".".join(str(part) for part in version)
