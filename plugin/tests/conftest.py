"""Shared fixtures of the plugin's tests."""

from pathlib import Path

import pytest

from coloqo import trail


@pytest.fixture(autouse=True)
def trail_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep sessions' trail marks in a temporary directory, never in the person's own.

    Tests run inside Claude Code sessions too, where the current session is known: a tool that
    writes to Coloqo would otherwise mark the very session running the tests.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
    """
    folder = tmp_path / "trail-config"
    monkeypatch.setattr(trail, "config_dir", lambda: folder)
    return folder
