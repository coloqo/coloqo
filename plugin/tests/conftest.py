"""Shared fixtures of the plugin's tests."""

from pathlib import Path

import pytest

from coloqo import agents, trail


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


@pytest.fixture(autouse=True)
def agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test under Claude Code with no session seen, sessions kept in a temporary folder.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(agents, "_current", agents.Agent.Claude)
    monkeypatch.setattr(agents, "_seen", None)
    monkeypatch.setattr(agents, "_seen_at", 0.0)
    monkeypatch.setattr(agents, "config_dir", lambda: tmp_path / "agents-config")
    agents._find_agent.cache_clear()
