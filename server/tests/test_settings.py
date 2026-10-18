"""Tests of the instance settings."""

from pathlib import Path

import pytest

from coloqo_server import settings
from coloqo_server.settings import Settings


@pytest.fixture
def bundled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the bundled web directory to an empty temporary one.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.delenv("COLOQO_WEB_DIR", raising=False)
    monkeypatch.setattr(settings, "BUNDLED_WEB_DIR", tmp_path)
    return tmp_path


def test_web_dir_defaults_to_bundled_web(bundled: Path) -> None:
    """A release wheel serves the web it carries without any setting.

    Args:
        bundled: The bundled web directory.
    """
    (bundled / "index.html").write_text("<title>Coloqo</title>")

    assert Settings().web_dir == bundled


def test_web_dir_is_none_without_bundled_web(bundled: Path) -> None:
    """A development checkout carries no web: only the API is served.

    Args:
        bundled: The bundled web directory, left without ``index.html``.
    """
    assert Settings().web_dir is None


def test_web_dir_from_environment_wins(
    bundled: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``COLOQO_WEB_DIR`` overrides the bundled web.

    Args:
        bundled: The bundled web directory.
        tmp_path_factory: Factory of temporary directories from pytest.
        monkeypatch: Patching helper from pytest.
    """
    (bundled / "index.html").write_text("<title>Coloqo</title>")
    other = tmp_path_factory.mktemp("web")
    monkeypatch.setenv("COLOQO_WEB_DIR", str(other))

    assert Settings().web_dir == other
