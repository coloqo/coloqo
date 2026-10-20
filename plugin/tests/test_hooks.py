"""Tests of the reminder of a task's Topic when the work starts showing (decision 0023)."""

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from coloqo import hooks
from coloqo.api import ColoqoError, NotLoggedIn, Project

MINE, OTHER = 10, 20


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the plugin's configuration in a temporary directory.

    Args:
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
    """
    folder = tmp_path / "config"
    monkeypatch.setattr(hooks, "config_dir", lambda: folder)
    return folder


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
        """Answer the list of open Topics.

        Args:
            method: HTTP method.
            path: API path.
            **kwargs: Ignored.
        """
        FakeApi.asked.append(path)
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
    transcript: Path | None = None,
) -> None:
    """Run the hook for one tool call.

    Args:
        monkeypatch: Patching helper from pytest.
        tool: The tool's name.
        tool_input: Its arguments.
        transcript: The session's transcript.
    """
    data = {
        "session_id": "s1",
        "tool_name": tool,
        "tool_input": tool_input,
        "transcript_path": str(transcript) if transcript else None,
    }
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


def test_a_coloqo_write_is_found_in_the_transcript(tmp_path: Path) -> None:
    """A writing Coloqo tool in the transcript counts; reading or no transcript does not.

    Args:
        tmp_path: Temporary directory from pytest.
    """
    wrote, read = tmp_path / "wrote.jsonl", tmp_path / "read.jsonl"
    wrote.write_text(
        json.dumps({"type": "tool_use", "name": "mcp__plugin_coloqo_coloqo__note_stage"}) + "\n"
    )
    read.write_text(
        json.dumps({"type": "tool_use", "name": "mcp__plugin_coloqo_coloqo__read_topic"}) + "\n"
    )

    found = [hooks.wrote_to_coloqo(str(p)) for p in (wrote, read, tmp_path / "gone.jsonl")]

    assert [*found, hooks.wrote_to_coloqo(None)] == [True, False, False, False]


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


def test_a_subagent_is_not_reminded_and_leaves_the_session_unmarked(
    config: Path,
    project: Path,
    server: type[FakeApi],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A subagent's change neither gets the reminder nor uses up the conversation's one.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    data = {
        "session_id": "s1",
        "agent_id": "a1",
        "tool_name": "Bash",
        "tool_input": {"command": "git push"},
    }
    monkeypatch.setattr(hooks, "_input", lambda: data)
    hooks.post_tool_use()
    in_subagent = capsys.readouterr().out
    _call(monkeypatch, "Bash", {"command": "git push"})

    assert in_subagent == ""
    assert "you hold T-12" in capsys.readouterr().out


def test_a_session_that_holds_nothing_is_told_to_open_a_topic() -> None:
    """Without held Topics the reminder says to open one, or say why none is needed."""
    line = hooks.reminder([])

    assert "open its Topic with open_topic" in line
    assert "tell your user in one line why" in line


def test_a_session_that_wrote_to_coloqo_is_not_reminded(
    config: Path,
    project: Path,
    server: type[FakeApi],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A session that opened or noted a Topic needs no reminder and asks the server nothing.

    Args:
        config: The configuration directory.
        project: The project directory.
        server: The fake server.
        tmp_path: Temporary directory from pytest.
        monkeypatch: Patching helper from pytest.
        capsys: Captured output from pytest.
    """
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('{"name": "mcp__plugin_coloqo_coloqo__open_topic"}\n')

    _call(monkeypatch, "Bash", {"command": "git push"}, transcript)

    assert capsys.readouterr().out == ""
    assert server.asked == []
    assert (config / "reminded" / "s1").exists()


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
    assert (config / "reminded" / "s1").exists()


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
    assert (config / "reminded" / "s1").exists()


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
