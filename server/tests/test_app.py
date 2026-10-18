"""Tests of the application as a whole."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coloqo_server.app import create_app
from coloqo_server.settings import Settings


@pytest.fixture
def web_dir(tmp_path: Path) -> Path:
    """A built web interface: an entry page and one hashed asset.

    Args:
        tmp_path: Temporary directory from pytest.
    """
    (tmp_path / "index.html").write_text("<title>Coloqo</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)")
    return tmp_path


def test_health() -> None:
    """The health check answers without the web interface configured."""
    client = TestClient(create_app(Settings(web_dir=None)))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_without_web_dir_root_is_not_served() -> None:
    """Without ``web_dir`` the server is the API only."""
    client = TestClient(create_app(Settings(web_dir=None)))

    assert client.get("/").status_code == 404


def test_root_serves_entry_page(web_dir: Path) -> None:
    """``/`` is the web interface's entry page."""
    client = TestClient(create_app(Settings(web_dir=web_dir)))

    response = client.get("/")

    assert response.status_code == 200
    assert "<title>Coloqo</title>" in response.text


def test_client_route_falls_back_to_entry_page(web_dir: Path) -> None:
    """A path routed on the client gets the entry page.

    Args:
        web_dir: The built web interface.
    """
    client = TestClient(create_app(Settings(web_dir=web_dir)))

    response = client.get("/teams/acme")

    assert response.status_code == 200
    assert "<title>Coloqo</title>" in response.text


def test_missing_asset_is_404(web_dir: Path) -> None:
    """A missing hashed asset is 404, not the entry page.

    Args:
        web_dir: The built web interface.
    """
    client = TestClient(create_app(Settings(web_dir=web_dir)))

    assert client.get("/assets/index-abc.js").status_code == 200
    assert client.get("/assets/index-old.js").status_code == 404


def test_api_is_not_shadowed_by_web(web_dir: Path) -> None:
    """The API answers next to the web interface; an unknown API path is 404.

    Args:
        web_dir: The built web interface.
    """
    client = TestClient(create_app(Settings(web_dir=web_dir)))

    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/no-such-route").status_code == 404
