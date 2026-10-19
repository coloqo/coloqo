"""What reaches a session unasked: its focus, kept on this computer (decision 0022)."""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coloqo.config import config_dir

MODES = ("all", "mine", "people", "quiet")
"""``all``: the Team; ``mine``: Topics this project's Assistant holds or writes in; ``people``:
Messages of some people and their Assistants; ``quiet``: nothing."""

STALE_SECONDS = 14 * 24 * 3600
"""A focus file of a session not touched this long is removed."""


@dataclass
class Focus:
    """A session's focus.

    Attributes:
        mode: One of ``MODES``.
        people: Pseudonyms followed in the ``people`` mode.
    """

    mode: str = "all"
    people: list[str] = field(default_factory=list)

    def describe(self) -> str:
        """Return the focus as a person would say it."""
        if self.mode == "people":
            return "people: " + ", ".join(self.people)
        return self.mode


def session_id() -> str | None:
    """Return the Claude Code session the process runs in, when Claude Code says so."""
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def _folder() -> Path:
    """Return where sessions' focus files live."""
    return config_dir() / "focus"


def _settings() -> dict[str, Any]:
    """Return the plugin's settings on this computer; empty when there are none."""
    try:
        return json.loads((config_dir() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def parse(text: str) -> Focus:
    """Read a focus as people write it: ``all``, ``mine``, ``quiet``, or names for ``people``.

    Args:
        text: E.g. ``mine``, ``bob``, ``people: bob, carol``, ``bob carol``.

    Raises:
        ValueError: Nothing to read.
    """
    words = text.replace(",", " ").replace(":", " ").split()
    if not words:
        raise ValueError("Say all, mine, quiet, or the people to follow")
    head = words[0].lower()
    if head in ("all", "mine", "quiet") and len(words) == 1:
        return Focus(head)
    names = words[1:] if head == "people" else words
    if not names:
        raise ValueError("Name the people to follow, e.g. `people: bob, carol`")
    return Focus("people", [name.lstrip("@") for name in names])


def default() -> Focus:
    """Return the focus new sessions start with: ``default_focus`` in the settings, or ``all``."""
    try:
        return parse(str(_settings().get("default_focus") or "all"))
    except ValueError:
        return Focus()


def load(session: str | None = None) -> Focus:
    """Return a session's focus; the default when it has none or the session is unknown.

    Args:
        session: The session; the current one when omitted.
    """
    session = session or session_id()
    if not session:
        return default()
    try:
        data = json.loads((_folder() / f"{session}.json").read_text(encoding="utf-8"))
        focus = Focus(str(data["mode"]), [str(p) for p in data.get("people", [])])
    except (OSError, ValueError, KeyError, TypeError):
        return default()
    return focus if focus.mode in MODES else default()


def save(focus: Focus, session: str | None = None) -> Path:
    """Remember a session's focus, and forget those of long-gone sessions.

    Args:
        focus: The focus.
        session: The session; the current one when omitted.

    Raises:
        ValueError: The session is not known.
        OSError: The file cannot be written.
    """
    session = session or session_id()
    if not session:
        raise ValueError("Claude Code did not say which session this is")
    folder = _folder()
    folder.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in folder.glob("*.json"):
        if now - old.stat().st_mtime > STALE_SECONDS:
            old.unlink(missing_ok=True)
    path = folder / f"{session}.json"
    path.write_text(json.dumps({"mode": focus.mode, "people": focus.people}), encoding="utf-8")
    return path


def allows(focus: Focus, kind: str, data: dict[str, Any], assistant_id: int) -> bool:
    """Whether an event may reach a session with this focus; the watch asks before printing.

    Args:
        focus: The session's focus.
        kind: Event kind.
        data: Event data.
        assistant_id: This project's Assistant.
    """
    if focus.mode == "all":
        return True
    if focus.mode == "quiet":
        return False
    if focus.mode == "mine":
        involved = set(data.get("assistant_ids") or []) | {data.get("holder_assistant_id")}
        return assistant_id in involved or data.get("to_assistant_id") == assistant_id
    author = str(data.get("author") or "").lower()
    return kind in ("message", "topic") and author in {p.lower() for p in focus.people}
