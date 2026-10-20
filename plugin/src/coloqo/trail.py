"""Whether a session keeps its task's trail in Coloqo, kept on this computer (decision 0023).

Two marks per Claude Code session. ``done``: the session wrote to Coloqo, was reminded, or needs
no reminder. ``pending``: a subagent of the session changed what the team will see, and the
conversation is to be reminded at its next watched tool call or prompt. The MCP server sets
``done`` on each write, so a write made by a subagent or a fork counts for the whole session.
"""

import time
from pathlib import Path

from coloqo import focus
from coloqo.config import config_dir

STALE_SECONDS = 14 * 24 * 3600
"""A mark of a session not touched this long is removed."""


def _mark(kind: str, session: str) -> Path:
    """Return the file of a session's mark.

    Args:
        kind: ``done`` or ``pending``.
        session: The Claude Code session.
    """
    return config_dir() / "trail" / kind / session


def _touch(path: Path) -> None:
    """Create a mark, and forget the marks of long-gone sessions; a failure is ignored.

    Args:
        path: The mark.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for old in path.parent.iterdir():
            if now - old.stat().st_mtime > STALE_SECONDS:
                old.unlink(missing_ok=True)
        path.touch()
    except OSError:
        pass


def is_done(session: str) -> bool:
    """Whether the session needs no more reminders.

    Args:
        session: The Claude Code session.
    """
    return _mark("done", session).exists()


def is_pending(session: str) -> bool:
    """Whether a subagent of the session changed what the team will see.

    Args:
        session: The Claude Code session.
    """
    return _mark("pending", session).exists()


def mark_done(session: str | None = None) -> None:
    """Mark a session as needing no more reminders; nothing without a known session.

    Args:
        session: The session; the current one when omitted.
    """
    session = session or focus.session_id()
    if session:
        _touch(_mark("done", session))


def mark_pending(session: str) -> None:
    """Mark that a subagent of the session changed what the team will see.

    Args:
        session: The Claude Code session.
    """
    _touch(_mark("pending", session))
