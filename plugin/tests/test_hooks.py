"""Tests of the reminder of a task's Topic when the work starts showing (decision 0023)."""

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from coloqo import focus, hooks, mcp_server, trail
from coloqo.api import ColoqoError, NotLoggedIn, Project

MINE, OTHER = 10, 20


@pytest.fixture
def config(trail_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the plugin's configuration, the focus included, in a temporary directory.

    Args:
        trail_dir: Where the trail marks are kept.
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(focus, "config_dir", lambda: trail_dir)
    return trail_dir


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make a project directory and tell the hook it is Claude Code's project.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
    """
    folder = (tmp_path / "web-app").resolve()
    folder.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(folder))
    return folder


class FakeApi:
    """Stands in for the server when the hook asks which Topics the Assistant holds.

    Attributes:
        team_id: The Team the project is linked to; ``None`` while unlinked.
        down: Whether the server is unreachable.
        logged_out: Whether the computer is not logged in.
        asked: Paths requested.
    """

    team_id: int | None = 1
    down = False
    logged_out = False
    asked: ClassVar[list[str]] = []

    def __init__(self, timeout: float) -> None:
        """Start a session with the server.

        Args:
            timeout: Ignored.
        """
        self.assistant_id = MINE

    def register(self, project: Project) -> str:
        """Pretend to register.

        Args:
            project: The project.

        Raises:
            NotLoggedIn: The computer is not logged in.
            ColoqoError: The server is down.
        """
        if FakeApi.logged_out:
            raise NotLoggedIn(401, "not logged in")
        if FakeApi.down:
            raise ColoqoError(0, "unreachable")
        return "alice · web-app"

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        """Answer the Inbox (empty) and the list of open Topics.

        Args:
            method: HTTP method.
            path: API path.
            **kwargs: Ignored.
        """
        FakeApi.asked.append(path)
        if path == "/inbox":
            return []
        return [
            {"ref": "T-12", "title": "Fix export", "issue": "ACME-42", "holder_assistant_id": MINE},
            {"ref": "T-13", "title": "Not mine", "issue": "", "holder_assistant_id": OTHER},
        ]

    def close(self) -> None:
        """Nothing to close."""


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> type[FakeApi]:
    """Put the fake server in place, linked and reachable.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setattr(hooks, "Api", FakeApi)
    FakeApi.team_id, FakeApi.down, FakeApi.logged_out, FakeApi.asked = 1, False, False, []
    return FakeApi


def _call(
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    tool_input: dict[str, Any],
    agent: str | None = None,
) -> None:
    """Run the hook for one tool call.

    Args:
        monkeypatch: Patching helper from pytest.
        tool: The tool's name.
        tool_input: Its arguments.
        agent: The subagent or fork making the call; ``None`` for the conversation itself.
    """
    data = {"session_id": "s1", "tool_name": tool, "tool_input": tool_input}
    if agent:
        data["agent_id"] = agent
    monkeypatch.setattr(hooks, "_input", lambda: data)
    hooks.post_tool_use()


@pytest.mark.parametrize(
    ("tool", "tool_input", "expected"),
    [
        ("Edit", {"file_path": "{project}/src/app.py"}, True),
        ("Write", {"file_path": "docs/readme.md"}, True),
        ("NotebookEdit", {"notebook_path": "{project}/a.ipynb"}, True),
        ("Edit", {"file_path": "/home/alice/.claude/memory/note.md"}, False),
        ("Edit", {"file_path": "{project}/../other/app.py"}, False),
        ("Read", {"file_path": "{project}/src/app.py"}, False),
        ("Bash", {"command": "git commit -m 'Fix export'"}, True),
        ("Bash", {"command": "git -C billing push origin fix-export"}, True),
        ("Bash", {"command": "git checkout -b fix-export"}, True),
        ("Bash", {"command": "git switch -c fix-export"}, True),
        ("Bash", {"command": "gh pr create --fill"}, True),
        ("Bash", {"command": "glab mr create"}, True),
        ("Bash", {"command": "git status && git log --grep=commit"}, False),
        ("Bash", {"command": "git fetch origin push-fix"}, False),
        ("Bash", {"command": "git log | grep push"}, False),
        ("mcp__atlassian__createJiraIssue", {}, True),
        ("mcp__atlassian__transitionJiraIssue", {}, True),
        ("mcp__tracker__add_comment", {}, True),
        ("mcp__claude_ai_Gmail__send_message", {}, True),
        ("mcp__atlassian__getJiraIssue", {}, False),
        ("mcp__plugin_coloqo_coloqo__close_topic", {}, False),
    ],
)
def test_a_change_the_team_will_see_is_told_apart(
    project: Path, tool: str, tool_input: dict[str, str], expected: bool
) -> None:
    """Files in the project, git and review writes, writing tools of other servers count.

    Args:
        project: The project directory.
        tool: The tool's name.
        tool_input: Its arguments, with ``{project}`` for the project directory.
        expected: Whether the call counts.
    """
    filled = {k: v.replace("{project}", str(project)) for k, v in tool_input.items()}

    assert hooks.visible_change(tool, filled, project) is expected


def test_the_session_is_reminded_once_with_its_held_topics(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The first visible change names the Topics this Assistant holds; the next stays silent.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    _call(monkeypatch, "Bash", {"command": "git status"})
    unseen = capsys.readouterr().out
    _call(monkeypatch, "Bash", {"command": "git checkout -b fix-export"})
    first = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    _call(monkeypatch, "Edit", {"file_path": str(project / "app.py")})
    second = capsys.readouterr().out

    assert unseen == ""
    assert first["hookEventName"] == "PostToolUse"
    assert "you hold T-12 «Fix export» [ACME-42])" in first["additionalContext"]
    assert "T-13" not in first["additionalContext"]
    assert second == ""
    assert len(server.asked) == 1


def test_a_subagents_change_is_told_to_the_conversation_at_its_next_call(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fork's change is not reminded in the fork; the conversation hears it next.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    _call(monkeypatch, "Bash", {"command": "git push"}, agent="a1")
    in_fork = capsys.readouterr().out
    _call(monkeypatch, "Bash", {"command": "ls"})

    assert in_fork == ""
    assert "you hold T-12" in capsys.readouterr().out
    assert trail.is_done("s1")


def test_a_subagent_that_changes_nothing_visible_leaves_nothing_pending(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A subagent reading or running tests marks nothing, so the conversation stays quiet.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    _call(monkeypatch, "Bash", {"command": "uv run pytest"}, agent="a1")
    _call(monkeypatch, "Bash", {"command": "ls"})

    assert capsys.readouterr().out == ""
    assert server.asked == []


def test_the_prompt_tells_the_conversation_of_a_subagents_change(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the conversation makes no call after a fork's change, the next prompt carries it.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    _call(monkeypatch, "Edit", {"file_path": str(project / "app.py")}, agent="a1")
    capsys.readouterr()
    monkeypatch.setattr(hooks, "_input", lambda: {"session_id": "s1"})
    hooks.user_prompt_submit()
    first = capsys.readouterr().out
    hooks.user_prompt_submit()

    assert "you hold T-12" in first
    assert capsys.readouterr().out == ""


def test_a_session_that_holds_nothing_is_told_to_open_a_topic() -> None:
    """Without held Topics the reminder says to open one, or say why none is needed."""
    line = hooks.reminder([])

    assert "open its Topic with open_topic" in line
    assert "tell your user in one line why" in line


def test_a_session_that_wrote_to_coloqo_is_not_reminded(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A session the MCP server marked on a write needs no reminder and asks the server nothing.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    trail.mark_done("s1")

    _call(monkeypatch, "Bash", {"command": "git push"})

    assert capsys.readouterr().out == ""
    assert server.asked == []


class ServerAnswers:
    """Answers every request of a Coloqo tool with a Topic, a Message and a closing at once."""

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Answer with every field the tools read back.

        Args:
            method: HTTP method.
            path: API path.
            **kwargs: Ignored.
        """
        return {
            "ref": "T-3",
            "title": "Fix",
            "area": "Dev",
            "status": "open",
            "number": 6,
            "last_number": 6,
            "files": [],
            "messages": [],
            "turns_since_human": 0,
            "turn_limit": 8,
            "deletes_at": "2026-10-27T10:00:00Z",
        }


@pytest.mark.parametrize(
    ("tool", "writes"),
    [
        (lambda: mcp_server.open_topic(1, "Fix export", "Took ACME-42"), True),
        (lambda: mcp_server.post_message("T-3", 6, "Done."), True),
        (lambda: mcp_server.hold_topic("T-3"), True),
        (lambda: mcp_server.note_stage("T-3", "code in billing"), True),
        (lambda: mcp_server.close_topic("T-3", "Fixed in ACME-42"), True),
        (lambda: mcp_server.read_topic("T-3"), False),
    ],
    ids=["open_topic", "post_message", "hold_topic", "note_stage", "close_topic", "read_topic"],
)
def test_a_write_to_coloqo_marks_the_session(
    trail_dir: Path, monkeypatch: pytest.MonkeyPatch, tool: Any, writes: bool
) -> None:
    """Each writing tool marks the session it runs in, a fork's included; reading does not.

    Args:
        trail_dir: Where the trail marks are kept.
        monkeypatch: Patching helper from pytest.
        tool: Calls the tool.
        writes: Whether the tool writes to Coloqo.
    """
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setattr(mcp_server, "_client", ServerAnswers)

    tool()

    assert trail.is_done("s1") is writes


def test_a_computer_not_logged_in_is_not_reminded(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without a login Coloqo cannot be written to, so the session is marked and stays silent.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    server.logged_out = True

    _call(monkeypatch, "Bash", {"command": "git push"})

    assert capsys.readouterr().out == ""
    assert trail.is_done("s1")


def test_an_unlinked_project_is_not_reminded(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unlinked project writes nowhere, so its session is marked and stays silent.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    server.team_id = None

    _call(monkeypatch, "Bash", {"command": "git push"})

    assert capsys.readouterr().out == ""
    assert server.asked == []
    assert trail.is_done("s1")


def test_an_unreachable_server_leaves_the_reminder_for_later(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the server cannot be reached the session is not marked, and the next change tries.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    server.down = True
    _call(monkeypatch, "Bash", {"command": "git push"})
    silent = capsys.readouterr().out
    server.down = False
    _call(monkeypatch, "Bash", {"command": "git push"})

    assert silent == ""
    assert "you hold T-12" in capsys.readouterr().out
