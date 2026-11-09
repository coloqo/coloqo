"""The agent that drives the plugin: Claude Code, Codex or Qwen Code (decision 0035).

Claude Code loads the plugin; Codex and Qwen Code get its hooks and MCP server from the installer,
which passes ``--agent`` to each command. The agent decides where the session id and the project
directory come from. Without ``--agent`` the agent is Claude Code, so the Claude Code plugin's
pinned commands work as before.
"""

import contextlib
import functools
import os
import subprocess
import time
from enum import StrEnum
from pathlib import Path

from coloqo.config import config_dir


class Agent(StrEnum):
    """An agent the plugin runs under.

    Attributes:
        Claude: Claude Code, through its plugin.
        Codex: OpenAI's Codex CLI, set up by the installer.
        Qwen: Qwen Code, set up by the installer.
    """

    Claude = "claude"
    Codex = "codex"
    Qwen = "qwen"


SESSION_ENV = {Agent.Claude: "CLAUDE_CODE_SESSION_ID", Agent.Qwen: "QWEN_CODE_SESSION_ID"}
"""The variable that names the session, in hooks and the MCP server alike. Codex sets none."""

PROJECT_ENV = {Agent.Claude: "CLAUDE_PROJECT_DIR", Agent.Qwen: "QWEN_PROJECT_DIR"}
"""The variable hooks get with the project directory. Qwen's ``QWEN_CODE_PROJECT_DIR`` is its own
storage, not the project; Codex sets none and gives ``cwd`` in the hook's input."""

PROCESS_NAMES = {Agent.Codex: frozenset({"codex", "codex.exe"})}
"""Names of the agent's process, the parent its hooks and its MCP server share."""

STALE_SECONDS = 14 * 24 * 3600
"""A remembered session not touched this long is removed."""

_current = Agent.Claude
_seen: str | None = None


def use(agent: Agent) -> None:
    """Set the agent this process serves, from the command's ``--agent``.

    Args:
        agent: The agent.
    """
    global _current
    _current = agent


def current() -> Agent:
    """Return the agent this process serves."""
    return _current


def seen(session: str | None) -> None:
    """Note the session a request to the MCP server names, as Codex does in ``_meta``.

    Args:
        session: The session id; ``None`` or empty changes nothing.
    """
    global _seen
    if session:
        _seen = str(session)


def session_id() -> str | None:
    """Return the session this process serves, when the agent tells it (decision 0024).

    Claude Code and Qwen Code name it in the environment. Codex names it only in hooks' input and
    in tool calls' ``_meta``; before the first tool call the MCP server finds what its hooks left
    under their shared parent.
    """
    agent = current()
    variable = SESSION_ENV.get(agent)
    if variable:
        return os.environ.get(variable) or None
    return _seen or remembered()


def project_dir() -> str | None:
    """Return the project directory the agent names in the environment, if it does."""
    variable = PROJECT_ENV.get(current())
    return (os.environ.get(variable) or None) if variable else None


def _parents() -> list[tuple[int, str]]:
    """Return this process's ancestors as ``(pid, name)``, nearest first.

    Read from ``/proc`` on Linux and from ``ps`` elsewhere on Unix; empty on Windows or when the
    system does not say.
    """
    chain: list[tuple[int, str]] = []
    pid = os.getpid()
    for _ in range(8):
        parent = _parent(pid)
        if parent is None:
            break
        pid, name = parent
        if pid <= 1:
            break
        chain.append((pid, name))
    return chain


def _parent(pid: int) -> tuple[int, str] | None:
    """Return a process's parent as ``(pid, name)``; ``None`` when unknown.

    Args:
        pid: The process.
    """
    if os.name == "nt":
        return None
    stat = Path(f"/proc/{pid}/stat")
    try:
        if stat.exists():
            text = stat.read_text()
            ppid = int(text[text.rindex(")") + 2 :].split()[1])
            parent = Path(f"/proc/{ppid}/stat").read_text()
            return ppid, parent[parent.index("(") + 1 : parent.rindex(")")]
        out = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True, timeout=2
        ).stdout.strip()
        ppid = int(out)
        name = subprocess.run(
            ["ps", "-o", "comm=", "-p", str(ppid)], capture_output=True, text=True, timeout=2
        ).stdout.strip()
        return ppid, os.path.basename(name)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def agent_pid() -> int | None:
    """Return the pid of the agent's process above this one; ``None`` when not found.

    Looked up once per process and agent: the parent does not change, and on macOS each level is
    two ``ps`` runs, which an MCP server would otherwise repeat at every call.
    """
    return _find_agent(current())


@functools.cache
def _find_agent(agent: Agent) -> int | None:
    """Return the pid of the nearest ancestor that is the agent's process; ``None`` if none.

    Args:
        agent: The agent whose process names to look for.
    """
    names = PROCESS_NAMES.get(agent)
    if not names:
        return None
    for pid, name in _parents():
        if name.lower() in names:
            return pid
    return None


def _session_file(pid: int) -> Path:
    """Return the file where hooks leave the session of an agent's process.

    Args:
        pid: The agent's process.
    """
    return config_dir() / "sessions" / f"{current()}-{pid}"


def remember(session: str) -> None:
    """Leave the session under the agent's process, for its MCP server; only for Codex.

    A failure is ignored: the MCP server then learns the session at its first tool call.

    Args:
        session: The session a hook serves.
    """
    if current() is not Agent.Codex or not session:
        return
    pid = agent_pid()
    if pid is None:
        return
    path = _session_file(pid)
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for old in path.parent.iterdir():
            if now - old.stat().st_mtime > STALE_SECONDS:
                old.unlink(missing_ok=True)
        path.write_text(session, encoding="utf-8")


def remembered() -> str | None:
    """Return the session hooks left under this process's agent; ``None`` when there is none."""
    pid = agent_pid()
    if pid is None:
        return None
    try:
        return _session_file(pid).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def skill(name: str) -> str:
    """Return how the user invokes a Coloqo command in the agent: ``/coloqo:focus`` and the like.

    Args:
        name: ``focus`` or ``link``.
    """
    return {
        Agent.Claude: f"/coloqo:{name}",
        Agent.Codex: f"$coloqo-{name}",
        Agent.Qwen: f"/coloqo-{name}",
    }[current()]
