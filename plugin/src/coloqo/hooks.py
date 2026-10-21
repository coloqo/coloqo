"""Claude Code hooks: what the session learns at start, on each prompt, and when its work
starts showing to the team (decisions 0006, 0023).

A hook never fails the session: on any problem it prints a short note or nothing and exits 0.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from coloqo import focus, trail
from coloqo.api import Api, ColoqoError, NotLoggedIn, Project
from coloqo.render import topic_line

FILE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
"""Tools that change a file; a change inside the project is a change the team will see."""

SHELL_TOOLS = frozenset({"Bash", "PowerShell"})
"""Tools that run shell commands: Bash, and PowerShell, which Claude Code uses on Windows."""

GIT_WRITE = re.compile(
    r"\bgit\b[^;&|\n]*?\s(?:commit|push|checkout\s+-b|switch\s+-c)(?=\s|$)"
    r"|\b(?:gh\s+pr|glab\s+mr)\s+create(?=\s|$)"
)
"""Shell commands that make a commit, a push, a branch, a pull or merge request."""

WRITE_VERBS = frozenset({"create", "update", "transition", "edit", "close", "comment", "send"})
"""Words in another MCP server's tool name that mark a write: a tracker, mail, documents."""

LOGIN_HINT = (
    "Coloqo plugin is installed, but this computer is not logged in to Coloqo. If the user wants "
    "to use Coloqo, they run `uvx coloqo login` in a terminal (or `! uvx coloqo login` here) "
    "and confirm the code in the browser, then restart the session."
)


def _input() -> dict[str, Any]:
    """Return the hook's JSON input from standard input; empty when there is none."""
    try:
        return json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}


def session_start() -> None:
    """Register the project's Assistant and tell the session what the server briefs it with.

    A linked project gets Coloqo's rules, its held Topics, the Inbox and the session's focus;
    an unlinked one a single quiet line (decisions 0020, 0021, 0022).
    """
    data = _input()
    api = Api(timeout=8)
    try:
        api.register(Project.detect(str(_project(data))), _session(data) or None)
        briefing = api.request("GET", "/briefing")
        unread = api.request("GET", "/inbox") if briefing.get("team") else []
    except NotLoggedIn:
        print(LOGIN_HINT)
        return
    except ColoqoError as error:
        print(f"Coloqo is unreachable right now ({error}); its tools may fail.")
        return
    finally:
        api.close()
    lines = [briefing["text"]]
    if briefing.get("team"):
        current = focus.load(data.get("session_id"))
        if unread:
            lines.append(f"Inbox — {len(unread)} topics with unread messages:")
            lines.extend(f"- {topic_line(t, api.team, api.assistant_key)}" for t in unread[:10])
            lines.append("Mention them to the user; read with the coloqo read_topic tool.")
        lines.append(
            f"This session's Coloqo focus: {current.describe()} (what reaches it unasked; the "
            "user changes it with /coloqo:focus or by asking you to call set_focus)."
        )
    print("\n".join(lines))


def user_prompt_submit() -> None:
    """Remind the session of Topics addressed to the user that its focus lets through.

    Also of its task's Topic, when a subagent of the session changed what the team will see and
    the conversation has not been told yet (decision 0023). And note that a turn starts with a
    prompt, the user's or one made from an event (decision 0026).
    """
    data = _input()
    session = _session(data)
    if session:
        trail.prompt_arrived(session, str(data.get("prompt") or ""))
    if session and trail.is_pending(session) and not trail.is_done(session):
        line = task_reminder(session, _project(data))
        if line:
            print(line)
    current = focus.load(data.get("session_id"))
    if current.mode == "quiet":
        return
    api = Api(timeout=3)
    try:
        api.register(Project.detect(str(_project(data))), session or None)
        unread = api.request("GET", "/inbox")
    except ColoqoError:
        return
    finally:
        api.close()
    addressed = [t for t in unread if t.get("addressed")]
    if current.mode == "mine":
        addressed = [t for t in addressed if t.get("holder_key") == api.assistant_key]
    elif current.mode == "people":
        people = {p.lower() for p in current.people}
        addressed = [t for t in addressed if str(t.get("created_by") or "").lower() in people]
    if addressed:
        lines = ["Coloqo — unread messages addressed to your user:"]
        lines.extend(f"- {topic_line(t, api.team, api.assistant_key)}" for t in addressed[:5])
        lines.append("Mention them briefly in your answer; read with read_topic when relevant.")
        print("\n".join(lines))


def _words(name: str) -> set[str]:
    """Return the lowercase words of a tool name: ``createJiraIssue``, ``send_message``.

    Args:
        name: The tool's name without its server.
    """
    return {w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name)}


def visible_change(tool: str, tool_input: dict[str, Any], project: Path) -> bool:
    """Whether a tool call changes what the team will see (decision 0023).

    A file changed inside the project, a commit, push, branch or pull request from the shell, or
    a writing tool of another MCP server: a tracker, mail, documents. The plugin knows no tracker;
    it reads the verbs in the tool's name.

    Args:
        tool: The tool's name, as Claude Code gives it.
        tool_input: Its arguments.
        project: The project directory.
    """
    if tool in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        return bool(path) and (project / str(path)).resolve().is_relative_to(project)
    if tool in SHELL_TOOLS:
        return bool(GIT_WRITE.search(str(tool_input.get("command") or "")))
    if tool.startswith("mcp__"):
        server, _, name = tool.removeprefix("mcp__").rpartition("__")
        return "coloqo" not in server.lower() and bool(WRITE_VERBS & _words(name))
    return False


def reminder(held: list[dict[str, Any]]) -> str:
    """Return the line that reminds a session of its task's Topic.

    Args:
        held: Open Topics the project's Assistant holds.
    """
    line = (
        "Coloqo: you are changing what the team sees, and this session has not written to "
        "Coloqo yet. "
    )
    if held:
        names = ", ".join(
            f"{t['ref']} «{t['title']}»" + (f" [{t['issue']}]" if t.get("issue") else "")
            for t in held[:5]
        )
        line += (
            f"If this is a task, note the stage in its Topic (you hold {names}) or open one "
            "with open_topic; "
        )
    else:
        line += "If this is a task, open its Topic with open_topic; "
    return line + "if it needs no Topic, tell your user in one line why."


def _session(data: dict[str, Any]) -> str:
    """Return the Claude Code session a hook serves; empty when Claude Code does not say.

    Args:
        data: The hook's input.
    """
    return str(data.get("session_id") or focus.session_id() or "")


def _project(data: dict[str, Any]) -> Path:
    """Return the project directory a hook serves.

    Args:
        data: The hook's input.
    """
    return Project.directory(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd"))


def task_reminder(session: str, project: Path) -> str | None:
    """Return the reminder of the task's Topic and mark the session; ``None`` when not needed.

    An unlinked project or a computer not logged in needs none, and the session is marked; an
    unreachable server leaves it unmarked, to try again later.

    Args:
        session: The Claude Code session.
        project: The project directory.
    """
    api = Api(timeout=3)
    try:
        api.register(Project.detect(str(project)), session)
        topics = (
            api.request("GET", f"/team/{api.team}/topic", params={"status": "open", "limit": 200})
            if api.team
            else None
        )
    except NotLoggedIn:
        trail.mark_done(session)
        return None
    except ColoqoError:
        return None
    finally:
        api.close()
    trail.mark_done(session)
    if topics is None:
        return None
    return reminder([t for t in topics if t.get("holder_key") == api.assistant_key])


def post_tool_use() -> None:
    """Remind the conversation of its task's Topic once, when its work starts showing to the team.

    Fires on the first tool call that changes what the team will see, in a session that has not
    written to Coloqo (the MCP server marks each write, decision 0023). A subagent's or a fork's
    change is not reminded where it happens: parallel forks would each be told and could open a
    Topic each, and it is the conversation that holds the Topic and talks to the user. It is
    marked pending instead, and the conversation hears it at its next call of a tool the hook
    watches (a file tool, `Bash`, an MCP tool) or at the next prompt.
    """
    data = _input()
    session = _session(data)
    if not session or trail.is_done(session):
        return
    tool_input = data.get("tool_input")
    project = _project(data)
    changed = visible_change(
        str(data.get("tool_name") or ""),
        tool_input if isinstance(tool_input, dict) else {},
        project,
    )
    if data.get("agent_id"):
        if changed:
            trail.mark_pending(session)
        return
    if not (changed or trail.is_pending(session)):
        return
    line = task_reminder(session, project)
    if line:
        output = {"hookEventName": "PostToolUse", "additionalContext": line}
        print(json.dumps({"hookSpecificOutput": output}, ensure_ascii=False))


def stop() -> None:
    """Note that the session's turn ended, so a turn a notification starts is told apart (0026)."""
    session = _session(_input())
    if session:
        trail.turn_ended(session)


HOOKS = {
    "session-start": session_start,
    "user-prompt-submit": user_prompt_submit,
    "post-tool-use": post_tool_use,
    "stop": stop,
}
