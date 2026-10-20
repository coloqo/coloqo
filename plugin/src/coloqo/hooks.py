"""Claude Code hooks: what the session learns at start, on each prompt, and when its work
starts showing to the team (decisions 0006, 0023).

A hook never fails the session: on any problem it prints a short note or nothing and exits 0.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from coloqo import focus
from coloqo.api import Api, ColoqoError, NotLoggedIn, Project
from coloqo.config import config_dir
from coloqo.render import topic_line

FILE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
"""Tools that change a file; a change inside the project is a change the team will see."""

GIT_WRITE = re.compile(
    r"\bgit\b[^;&|\n]*?\s(?:commit|push|checkout\s+-b|switch\s+-c)(?=\s|$)"
    r"|\b(?:gh\s+pr|glab\s+mr)\s+create(?=\s|$)"
)
"""Shell commands that make a commit, a push, a branch, a pull or merge request."""

WRITE_VERBS = frozenset({"create", "update", "transition", "edit", "close", "comment", "send"})
"""Words in another MCP server's tool name that mark a write: a tracker, mail, documents."""

COLOQO_WRITE = re.compile(
    r'"name":\s*"mcp__[^"]*coloqo[^"]*__'
    r'(?:open_topic|note_stage|post_message|hold_topic|close_topic)"'
)
"""A call of a Coloqo tool that writes, as the session's transcript records it."""

REMINDED_STALE_SECONDS = 14 * 24 * 3600
"""A reminder mark of a session not touched this long is removed."""

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
        api.register(Project.detect(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd")))
        briefing = api.request("GET", "/briefing")
        unread = api.request("GET", "/inbox") if briefing.get("team_id") else []
    except NotLoggedIn:
        print(LOGIN_HINT)
        return
    except ColoqoError as error:
        print(f"Coloqo is unreachable right now ({error}); its tools may fail.")
        return
    finally:
        api.close()
    lines = [briefing["text"]]
    if briefing.get("team_id"):
        current = focus.load(data.get("session_id"))
        if unread:
            lines.append(f"Inbox — {len(unread)} topics with unread messages:")
            lines.extend(f"- {topic_line(t)}" for t in unread[:10])
            lines.append("Mention them to the user; read with the coloqo read_topic tool.")
        lines.append(
            f"This session's Coloqo focus: {current.describe()} (what reaches it unasked; the "
            "user changes it with /coloqo:focus or by asking you to call set_focus)."
        )
    print("\n".join(lines))


def user_prompt_submit() -> None:
    """Remind the session of Topics addressed to the user that its focus lets through."""
    data = _input()
    current = focus.load(data.get("session_id"))
    if current.mode == "quiet":
        return
    api = Api(timeout=3)
    try:
        api.register(Project.detect(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd")))
        unread = api.request("GET", "/inbox")
    except ColoqoError:
        return
    finally:
        api.close()
    addressed = [t for t in unread if t.get("addressed")]
    if current.mode == "mine":
        addressed = [t for t in addressed if t.get("holder_assistant_id") == api.assistant_id]
    elif current.mode == "people":
        people = {p.lower() for p in current.people}
        addressed = [t for t in addressed if str(t.get("created_by") or "").lower() in people]
    if addressed:
        lines = ["Coloqo — unread messages addressed to your user:"]
        lines.extend(f"- {topic_line(t)}" for t in addressed[:5])
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
    if tool == "Bash":
        return bool(GIT_WRITE.search(str(tool_input.get("command") or "")))
    if tool.startswith("mcp__"):
        server, _, name = tool.removeprefix("mcp__").rpartition("__")
        return "coloqo" not in server.lower() and bool(WRITE_VERBS & _words(name))
    return False


def wrote_to_coloqo(transcript: str | None) -> bool:
    """Whether the session has already written to Coloqo, by its transcript.

    Args:
        transcript: Path of the session's transcript, as Claude Code gives it.
    """
    if not transcript:
        return False
    try:
        text = Path(transcript).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(COLOQO_WRITE.search(text))


def _reminded_mark(session: str) -> Path:
    """Return the file that marks a session as reminded or as needing no reminder.

    Args:
        session: The Claude Code session.
    """
    return config_dir() / "reminded" / session


def _remember(session: str) -> None:
    """Mark a session so that it is not reminded again, and forget long-gone sessions.

    Args:
        session: The Claude Code session.
    """
    mark = _reminded_mark(session)
    try:
        mark.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for old in mark.parent.iterdir():
            if now - old.stat().st_mtime > REMINDED_STALE_SECONDS:
                old.unlink(missing_ok=True)
        mark.touch()
    except OSError:
        pass


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


def post_tool_use() -> None:
    """Remind a session of its task's Topic once, when its work starts showing to the team.

    Fires on the first tool call that changes what the team will see, in a linked project, in a
    session that has not written to Coloqo; then the session is marked and the hook returns
    before the network. An unreachable server leaves the session unmarked, to try again on the
    next change (decision 0023).
    """
    data = _input()
    session = str(data.get("session_id") or focus.session_id() or "")
    if not session or _reminded_mark(session).exists():
        return
    project = Project.directory(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd"))
    tool_input = data.get("tool_input")
    if not visible_change(
        str(data.get("tool_name") or ""),
        tool_input if isinstance(tool_input, dict) else {},
        project,
    ):
        return
    if wrote_to_coloqo(data.get("transcript_path")):
        _remember(session)
        return
    api = Api(timeout=3)
    try:
        api.register(Project.detect(str(project)))
        topics = (
            api.request(
                "GET", f"/teams/{api.team_id}/topics", params={"status": "open", "limit": 200}
            )
            if api.team_id
            else None
        )
    except NotLoggedIn:
        _remember(session)
        return
    except ColoqoError:
        return
    finally:
        api.close()
    _remember(session)
    if topics is None:
        return
    held = [t for t in topics if t.get("holder_assistant_id") == api.assistant_id]
    output = {"hookEventName": "PostToolUse", "additionalContext": reminder(held)}
    print(json.dumps({"hookSpecificOutput": output}, ensure_ascii=False))


HOOKS = {
    "session-start": session_start,
    "user-prompt-submit": user_prompt_submit,
    "post-tool-use": post_tool_use,
}
