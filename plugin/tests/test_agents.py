"""Tests of Coloqo under Codex and Qwen Code: agents, hooks, MCP server, installer (0035)."""

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, ClassVar

import pytest

from coloqo import agents, cli, hooks, install, mcp_server
from coloqo.agents import Agent

CLAUDE_TEXTS = Path(__file__).resolve().parents[1] / "claude"


def test_each_agent_names_its_session_and_project_its_own_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude Code and Qwen Code name the session in the environment; Qwen's project is
    ``QWEN_PROJECT_DIR``, never its own storage in ``QWEN_CODE_PROJECT_DIR``; Codex names nothing.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "c-1")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/work/claude")
    monkeypatch.setenv("QWEN_CODE_SESSION_ID", "q-1")
    monkeypatch.setenv("QWEN_PROJECT_DIR", "/work/qwen")
    monkeypatch.setenv("QWEN_CODE_PROJECT_DIR", "/home/x/.qwen/projects/-work-qwen")
    monkeypatch.setattr(agents, "_parents", list)

    claude = (agents.session_id(), agents.project_dir())
    agents.use(Agent.Qwen)
    qwen = (agents.session_id(), agents.project_dir())
    agents.use(Agent.Codex)
    codex = (agents.session_id(), agents.project_dir())

    assert claude == ("c-1", "/work/claude")
    assert qwen == ("q-1", "/work/qwen")
    assert codex == (None, None)


def test_codex_hooks_leave_the_session_for_the_mcp_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Codex hook leaves its session under the ``codex`` process it shares with the MCP server,
    which reads it before any tool call; a tool call's ``_meta`` wins (decision 0035).

    Args:
        monkeypatch: Patching helper from pytest.
    """
    agents.use(Agent.Codex)
    monkeypatch.setattr(agents, "_parents", lambda: [(41, "uvx"), (40, "codex"), (7, "bash")])

    before = agents.session_id()
    hooks._session({"session_id": "codex-s1"})
    left = agents.session_id()
    agents.seen("codex-s2")

    assert (before, left, agents.session_id()) == (None, "codex-s1", "codex-s2")


def test_claude_hooks_leave_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Only Codex needs its session left; under Claude Code no file is written.

    Args:
        monkeypatch: Patching helper from pytest.
        tmp_path: Temporary directory from pytest.
    """
    monkeypatch.setattr(agents, "_parents", lambda: [(40, "codex")])

    hooks._session({"session_id": "c-9"})

    assert not (tmp_path / "agents-config").exists()


@pytest.mark.parametrize(
    ("tool", "tool_input", "expected"),
    [
        ("apply_patch", {"command": "*** Begin Patch\n*** Update File: /p/a.py\n@@\n-x\n+y"}, True),
        ("apply_patch", {"command": "*** Begin Patch\n*** Add File: docs/b.md\n+x"}, True),
        ("apply_patch", {"command": "*** Begin Patch\n*** Delete File: /etc/hosts\n"}, False),
        (
            "apply_patch",
            {"command": "*** Begin Patch\n*** Update File: /tmp/x\n*** Move to: c.py"},
            True,
        ),
        ("edit", {"file_path": "/p/a.py", "old_string": "x", "new_string": "y"}, True),
        ("write_file", {"file_path": "/elsewhere/a.py", "content": "x"}, False),
        ("run_shell_command", {"command": "git push origin main", "description": ""}, True),
        ("run_shell_command", {"command": "ls", "description": ""}, False),
    ],
)
def test_the_trail_knows_codex_and_qwen_tools(
    tool: str, tool_input: dict[str, Any], expected: bool
) -> None:
    """Codex's ``apply_patch`` names its files in the patch; Qwen's tools as Claude Code's (0023).

    Args:
        tool: The tool's name.
        tool_input: Its arguments.
        expected: Whether the team will see the change.
    """
    assert hooks.visible_change(tool, tool_input, Path("/p")) is expected


def test_the_briefing_names_the_agent_s_focus_skill() -> None:
    """The focus is changed by ``/coloqo:focus``, ``$coloqo-focus`` or ``/coloqo-focus``."""
    named = []
    for agent in Agent:
        agents.use(agent)
        named.append(agents.skill("focus"))

    assert named == ["/coloqo:focus", "$coloqo-focus", "/coloqo-focus"]


def test_the_mcp_server_notes_the_session_a_tool_call_names() -> None:
    """Codex's ``_meta.sessionId`` reaches the agent's session before the tool runs (0035)."""

    class Ctx:
        """A request context with raw parameters."""

        params: ClassVar[dict[str, Any]] = {
            "name": "inbox",
            "_meta": {"sessionId": "codex-7", "progressToken": 1},
        }

    async def handler(ctx: Any) -> str:
        """Answer with the session the tool would see.

        Args:
            ctx: The context.
        """
        return str(agents.session_id())

    agents.use(Agent.Codex)

    seen = asyncio.run(mcp_server.SessionFromMeta()(Ctx(), handler))

    assert seen == "codex-7"


class FakeApi:
    """Stands in for the client: records registrations and requests.

    Attributes:
        log: What happened, shared by all instances.
    """

    log: ClassVar[list[tuple[str, Any]]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Start unregistered.

        Args:
            *args: Ignored.
            **kwargs: Ignored.
        """
        self.assistant_key: str | None = None
        self.team = "acme"

    def register(self, project: Any, session: str | None = None) -> str:
        """Register as the session's Assistant.

        Args:
            project: The project.
            session: The session.
        """
        self.log.append(("register", session))
        self.assistant_key = f"key-{session}"
        return "alice · web · vega"

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Record a request.

        Args:
            method: HTTP method.
            path: API path.
            **kwargs: Body and the rest.
        """
        self.log.append((method, path))
        return {}

    def close(self) -> None:
        """Nothing to close."""


def test_the_tools_act_as_the_session_once_it_is_known(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Codex MCP server registered before it knew its session registers again as the session's
    own Assistant when a tool call names it (decision 0024).

    Args:
        monkeypatch: Patching helper from pytest.
    """
    agents.use(Agent.Codex)
    monkeypatch.setattr(agents, "_parents", list)
    monkeypatch.setattr(mcp_server, "Api", FakeApi)
    monkeypatch.setattr(mcp_server, "_api", None)
    monkeypatch.setattr(mcp_server, "_session", None)
    FakeApi.log = []

    first = mcp_server._client()
    again = mcp_server._client()
    agents.seen("codex-3")
    named = mcp_server._client()

    assert first is again
    assert named is not first
    assert FakeApi.log == [("register", None), ("register", "codex-3")]


def test_the_pulse_starts_once_the_session_is_known(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no session the pulse sends nothing; with one it calls as the session's Assistant and
    posts the move intervals the hooks logged (decisions 0029, 0033, 0035).

    Args:
        monkeypatch: Patching helper from pytest.
    """

    class Moves:
        """A log of moves with one finished interval."""

        def __init__(self, session: str) -> None:
            """Open the session's log.

            Args:
                session: The session.
            """

        def take(self) -> list[tuple[str, int, int]]:
            """Return the intervals finished since the last call."""
            return [("assistant", 1_000_000_000, 2_000_000_000)]

    agents.use(Agent.Codex)
    monkeypatch.setattr(agents, "_parents", list)
    monkeypatch.setattr(mcp_server, "Api", FakeApi)
    monkeypatch.setattr(mcp_server.trail, "MoveLog", Moves)
    FakeApi.log = []
    stop = threading.Event()
    stop.set()

    mcp_server.pulse(stop, seconds=0)
    silent = list(FakeApi.log)
    agents.seen("codex-5")
    mcp_server.pulse(stop, seconds=0)

    assert silent == []
    assert FakeApi.log == [
        ("register", "codex-5"),
        ("GET", "/assistant/key-codex-5"),
        ("POST", "/moves"),
    ]


def test_the_installer_keeps_other_hooks_and_replaces_its_own() -> None:
    """A second run replaces Coloqo's hooks of any version and keeps another tool's (0035)."""
    settings = {
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": "notify-send done"}]},
                {"hooks": [{"type": "command", "command": "uvx coloqo@0.1.0 hook stop"}]},
            ]
        }
    }

    once = install.merge_hooks(json.loads(json.dumps(settings)), Agent.Codex)
    twice = install.merge_hooks(json.loads(json.dumps(once)), Agent.Codex)
    commands = [h["command"] for g in twice["hooks"]["Stop"] for h in g["hooks"]]

    assert once == twice
    assert commands == ["notify-send done", f"{install.command(Agent.Codex, 'hook', 'stop')}"]
    assert twice["hooks"]["PostToolUse"][0]["matcher"] == "^(apply_patch|Bash|mcp__.*)$"
    assert twice["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] == 60


def test_installing_for_qwen_writes_its_settings_and_the_skills(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Qwen gets hooks and the MCP server in its user settings, other settings kept, and the three
    skills; no timeout, its own default (decision 0035).

    Args:
        monkeypatch: Patching helper from pytest.
        tmp_path: Temporary directory from pytest.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".qwen" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"model": {"name": "qwen3"}}))

    lines = install.install(Agent.Qwen)
    written = json.loads(settings.read_text())
    focus_skill = (tmp_path / ".agents/skills/coloqo-focus/SKILL.md").read_text()
    main_skill = (tmp_path / ".agents/skills/coloqo/SKILL.md").read_text()

    assert written["model"] == {"name": "qwen3"}
    assert written["mcpServers"]["coloqo"]["args"][-3:] == ["mcp", "--agent", "qwen"]
    hook = written["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    assert hook == {
        "type": "command",
        "command": install.command(Agent.Qwen, "hook", "user-prompt-submit"),
    }
    assert focus_skill.startswith("---\nname: coloqo-focus\n")
    assert "$ARGUMENTS" not in focus_skill
    assert "/coloqo-focus" in main_skill
    assert "/coloqo:focus" not in main_skill
    assert any("/hooks" in line for line in lines)


def test_installing_for_codex_adds_the_mcp_server_by_codex_itself(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Codex's MCP server goes through ``codex mcp add``, replacing an earlier one (0035).

    Args:
        monkeypatch: Patching helper from pytest.
        tmp_path: Temporary directory from pytest.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    ran: list[list[str]] = []

    class Done:
        """A finished command."""

        returncode = 0
        stdout = stderr = ""

    monkeypatch.setattr(install, "_run", lambda args: ran.append(args) or Done())

    install.install(Agent.Codex)
    written = json.loads((tmp_path / "codex" / "hooks.json").read_text())

    assert ran[0] == ["codex", "mcp", "remove", "coloqo"]
    assert ran[1][:5] == ["codex", "mcp", "add", "coloqo", "--"]
    assert ran[1][-3:] == ["mcp", "--agent", "codex"]
    assert "$coloqo-focus" in (tmp_path / ".agents/skills/coloqo/SKILL.md").read_text()
    assert set(written["hooks"]) == set(install.HOOKS)


def test_the_packaged_texts_are_the_claude_plugin_s() -> None:
    """The installer makes the skills from the same texts the Claude Code plugin ships."""
    packaged = Path(install.__file__).parent / "texts"

    assert (packaged / "skill.md").read_text() == (
        CLAUDE_TEXTS / "skills/coloqo/SKILL.md"
    ).read_text()
    for name in install.SKILLS:
        assert (packaged / f"{name}.md").read_text() == (
            CLAUDE_TEXTS / f"commands/{name}.md"
        ).read_text()


def test_the_commands_take_the_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--agent`` on a hook sets the agent the process serves.

    Args:
        monkeypatch: Patching helper from pytest.
    """
    served: list[Agent] = []
    monkeypatch.setitem(hooks.HOOKS, "stop", lambda: served.append(agents.current()))

    cli.main(["hook", "stop", "--agent", "qwen"])

    assert served == [Agent.Qwen]


def test_a_failed_pulse_keeps_what_is_unsent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A server failure makes the next pass register again, keeping the session's log of moves:
    what was not sent goes then, as the watch does after a break (decisions 0033, 0035).

    Args:
        monkeypatch: Patching helper from pytest.
    """
    opened: list[str] = []

    class Moves:
        """A log of moves that counts how often it is opened."""

        def __init__(self, session: str) -> None:
            """Open the session's log.

            Args:
                session: The session.
            """
            opened.append(session)

        def take(self) -> list[tuple[str, int, int]]:
            """Return the intervals finished since the last call."""
            return [("human", 1_000_000_000, 2_000_000_000)]

    class Flaky(FakeApi):
        """A client whose first call after registering fails."""

        failed = False

        def request(self, method: str, path: str, **kwargs: Any) -> Any:
            """Fail once, then record.

            Args:
                method: HTTP method.
                path: API path.
                **kwargs: Body and the rest.
            """
            if not Flaky.failed:
                Flaky.failed = True
                raise mcp_server.ColoqoError(502, "Bad gateway")
            return super().request(method, path, **kwargs)

    class TwoPasses:
        """A stop that lets the loop run twice."""

        def __init__(self) -> None:
            """Start with no pass made."""
            self.passes = 0

        def wait(self, seconds: float) -> bool:
            """Count a pass; stop after the second.

            Args:
                seconds: Ignored.
            """
            self.passes += 1
            return self.passes >= 2

    agents.use(Agent.Qwen)
    monkeypatch.setenv("QWEN_CODE_SESSION_ID", "q-2")
    monkeypatch.setattr(mcp_server, "Api", Flaky)
    monkeypatch.setattr(mcp_server.trail, "MoveLog", Moves)
    FakeApi.log = []

    mcp_server.pulse(TwoPasses(), seconds=0)  # type: ignore[arg-type]

    assert opened == ["q-2"]
    assert FakeApi.log == [
        ("register", "q-2"),
        ("register", "q-2"),
        ("GET", "/assistant/key-q-2"),
        ("POST", "/moves"),
    ]


def test_the_agent_s_process_is_looked_up_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP server finds the ``codex`` process once, not at every call (decision 0035).

    Args:
        monkeypatch: Patching helper from pytest.
    """
    walks: list[int] = []

    def parents() -> list[tuple[int, str]]:
        """Count the walk and return a ``codex`` parent."""
        walks.append(1)
        return [(40, "codex")]

    agents.use(Agent.Codex)
    monkeypatch.setattr(agents, "_parents", parents)

    pids = [agents.agent_pid() for _ in range(3)]

    assert (pids, len(walks)) == ([40, 40, 40], 1)
