"""Whether a session keeps its task's trail in Coloqo, kept on this computer (decision 0023).

Two marks per Claude Code session. ``done``: the session wrote to Coloqo, was reminded, or needs
no reminder. ``pending``: a subagent of the session changed what the team will see, and the
conversation is to be reminded at its next watched tool call or prompt. The MCP server sets
``done`` on each write, so a write made by a subagent or a fork counts for the whole session.

Two more tell who started the current turn (decision 0026): ``prompt``, written when a prompt
arrives, holding ``human`` or ``event`` and the time; and ``stop``, holding the time a turn
ended. The times are kept in the files, not taken from them: two writes within one tick of the
file system's clock would get the same modification time. Claude Code names
no turn's origin and runs the prompt hook for loop ticks and messages from other sessions too, so
the marks can only say when a turn was surely not the user's.

A last one, ``moves``, is a log the same two hooks append to, a line per prompt and per stop; the
session's watch reads what is new and posts the intervals of whose move it was (decision 0033).
Appending keeps the hooks off the network.
"""

import contextlib
import time
from pathlib import Path

from coloqo import focus
from coloqo.config import config_dir

EVENT_PROMPTS = (
    "<task-notification>",
    "<cross-session-message",
    "<agent-message",
    "<system-reminder>",
    "[SYSTEM NOTIFICATION",
)
"""How prompts that Claude Code makes from events, not from the user's typing, begin."""

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


def prompt_arrived(session: str, prompt: str) -> None:
    """Note that a turn starts with a prompt, the user's or one made from an event.

    Args:
        session: The Claude Code session.
        prompt: The prompt's text.
    """
    origin = "event" if prompt.lstrip().startswith(EVENT_PROMPTS) else "human"
    path = _mark("prompt", session)
    _touch(path)
    with contextlib.suppress(OSError):
        path.write_text(f"{origin} {time.time_ns()}", encoding="utf-8")


def turn_ended(session: str) -> None:
    """Note that the session's turn ended.

    Args:
        session: The Claude Code session.
    """
    path = _mark("stop", session)
    _touch(path)
    with contextlib.suppress(OSError):
        path.write_text(str(time.time_ns()), encoding="utf-8")


def human_turn(session: str) -> bool | None:
    """Whether the current turn was started by the user: ``False`` only when surely not.

    Not the user's when the last prompt came from an event, or when a turn ended after the last
    prompt and none came since (a notification started this one). ``None`` when the marks say
    nothing, as before the first prompt.

    Args:
        session: The Claude Code session.
    """
    try:
        origin, _, prompted = _mark("prompt", session).read_text(encoding="utf-8").partition(" ")
        prompted_at = int(prompted)
    except (OSError, ValueError):
        return None
    if origin == "event":
        return False
    try:
        if int(_mark("stop", session).read_text(encoding="utf-8")) >= prompted_at:
            return False
    except (OSError, ValueError):
        pass
    return True


Interval = tuple[str, int, int]
"""Whose move it was, ``assistant`` or ``human``, from and to, in nanoseconds."""


def log_move(session: str, mark: str) -> None:
    """Append a prompt or a stop to the session's log of moves; a failure is ignored.

    Args:
        session: The Claude Code session.
        mark: ``p`` for a prompt, ``s`` for a stop.
    """
    path = _mark("moves", session)
    _touch(path)
    with contextlib.suppress(OSError), path.open("a", encoding="utf-8") as log:
        log.write(f"{mark} {time.time_ns()}\n")


def intervals(
    marks: list[tuple[str, int]], last: tuple[str, int] | None
) -> tuple[list[Interval], tuple[str, int] | None]:
    """Turn prompts and stops into finished intervals; return them and the open mark.

    From a prompt to the next stop the move is the Assistant's; from a stop to the next prompt,
    the human's. A prompt made by an event counts as a prompt: the Assistant works on it. A
    repeated mark keeps the earlier one.

    Args:
        marks: New marks in order, ``(mark, nanoseconds)``.
        last: The mark the previous call left open.
    """
    found: list[Interval] = []
    for mark, moment in marks:
        if last is None or last[0] == mark:
            last = last or (mark, moment)
            continue
        found.append(("assistant" if last[0] == "p" else "human", last[1], moment))
        last = (mark, moment)
    return found, last


class MoveLog:
    """What the watch has read of its session's log of moves, kept in memory."""

    def __init__(self, session: str) -> None:
        """Start at the end of the log, so a restarted watch sends nothing twice.

        Args:
            session: The Claude Code session.
        """
        self.path = _mark("moves", session)
        self.offset = 0
        self.last: tuple[str, int] | None = None
        marks = self._read()
        self.last = marks[-1] if marks else None

    def _read(self) -> list[tuple[str, int]]:
        """Return the marks written since the last read, and move past them."""
        try:
            with self.path.open("rb") as log:
                if log.seek(0, 2) < self.offset:
                    # The log was removed and written anew: read it from its start.
                    self.offset = 0
                log.seek(self.offset)
                data = log.read()
        except OSError:
            return []
        end = data.rfind(b"\n") + 1
        self.offset += end
        marks = []
        for line in data[:end].decode("utf-8", "replace").splitlines():
            mark, _, moment = line.partition(" ")
            if mark in ("p", "s") and moment.isdigit():
                marks.append((mark, int(moment)))
        return marks

    def take(self) -> list[Interval]:
        """Return the intervals finished since the last call."""
        found, self.last = intervals(self._read(), self.last)
        return found
