"""The installer: Coloqo's hooks, MCP server and skills for Codex and Qwen Code (decision 0035).

Claude Code gets all of it from its plugin. Codex and Qwen Code have no plugin that carries hooks,
so ``coloqo install --agent codex|qwen`` writes it once per computer, at the user level, pinned to
the installer's own version, as the Claude Code plugin pins its commands. Running it again with a
newer version is the update; entries of other tools in the same files are kept.
"""

import json
import os
import re
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any

from coloqo import __version__
from coloqo.agents import Agent
from coloqo.config import load_token, server_url

HOOKS = {
    "SessionStart": "session-start",
    "UserPromptSubmit": "user-prompt-submit",
    "PostToolUse": "post-tool-use",
    "Stop": "stop",
}
"""The agent's hook events and the ``coloqo hook`` each runs."""

MATCHERS = {
    Agent.Codex: "^(apply_patch|Bash|mcp__.*)$",
    Agent.Qwen: "^(edit|write_file|run_shell_command|mcp__.*)$",
}
"""The tools PostToolUse watches: file edits, the shell and other MCP servers (decision 0023)."""

TIMEOUTS = {"SessionStart": 60}
"""Seconds a Codex hook may take; 10 for the rest. Qwen's are left at its default (0035)."""

OURS = re.compile(r"\bcoloqo(@[\w.]+)?\s+hook\b")
"""A hook command the installer wrote, of any version."""

SKILLS = ("focus", "link")
"""The Claude Code commands that become skills of their own."""


class InstallError(Exception):
    """The installer cannot finish: a file it must change cannot be read or written, or the
    agent's own command failed."""


def codex_home() -> Path:
    """Return Codex's settings folder: ``CODEX_HOME`` or ``~/.codex``."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def qwen_settings() -> Path:
    """Return Qwen Code's user settings file."""
    return Path.home() / ".qwen" / "settings.json"


def skills_home() -> Path:
    """Return the folder of the user's skills that Codex and Qwen Code both read."""
    return Path.home() / ".agents" / "skills"


def command(agent: Agent, *args: str) -> str:
    """Return a pinned ``coloqo`` command line for the agent.

    Args:
        agent: The agent.
        *args: The subcommand and its arguments.
    """
    return " ".join(["uvx", f"coloqo@{__version__}", *args, "--agent", str(agent)])


def merge_hooks(settings: dict[str, Any], agent: Agent) -> dict[str, Any]:
    """Return the settings with Coloqo's hooks for the agent, replacing older ones of Coloqo.

    Hooks of other tools stay as they are; a group left with no hooks is dropped.

    Args:
        settings: The parsed settings or hooks file, with a ``hooks`` object or none.
        agent: The agent.

    Raises:
        InstallError: ``hooks`` is not an object, or an event is not a list.
    """
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError("The settings' `hooks` is not an object; fix it by hand first")
    for event, name in HOOKS.items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise InstallError(f"The settings' hooks for {event} are not a list")
        kept = []
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get("hooks"), list):
                group["hooks"] = [
                    h
                    for h in group["hooks"]
                    if not (isinstance(h, dict) and OURS.search(str(h.get("command") or "")))
                ]
                if not group["hooks"]:
                    continue
            kept.append(group)
        entry: dict[str, Any] = {"type": "command", "command": command(agent, "hook", name)}
        if agent is Agent.Codex:
            entry["timeout"] = TIMEOUTS.get(event, 10)
        group = {"hooks": [entry]}
        if event == "PostToolUse":
            group = {"matcher": MATCHERS[agent], **group}
        kept.append(group)
        hooks[event] = kept
    return settings


def _read_json(path: Path) -> dict[str, Any]:
    """Return a JSON settings file as an object; empty when there is no file.

    Args:
        path: The file.

    Raises:
        InstallError: The file cannot be read, is not JSON (comments included) or not an object.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError) as error:
        raise InstallError(f"Cannot read {path} as JSON ({error}); fix it by hand first") from error
    if not isinstance(data, dict):
        raise InstallError(f"{path} is not a JSON object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a settings file, keeping the former one beside it as ``.bak``.

    Args:
        path: The file.
        data: Its new content.

    Raises:
        InstallError: The file cannot be written.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copyfile(path, path.with_name(path.name + ".bak"))
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as error:
        raise InstallError(f"Cannot write {path}: {error}") from error


def skill_text(name: str, agent: Agent) -> str:
    """Return a skill's ``SKILL.md`` for the agent, made from the Claude Code plugin's texts.

    ``coloqo`` is the plugin's skill with the agent's way to invoke the commands; ``focus`` and
    ``link`` are the plugin's commands as skills, ``coloqo-focus`` and ``coloqo-link``.

    Args:
        name: ``coloqo``, ``focus`` or ``link``.
        agent: The agent.

    Raises:
        OSError: The packaged text cannot be read.
    """
    prefix = "$" if agent is Agent.Codex else "/"
    texts = files("coloqo") / "texts"
    if name == "coloqo":
        text = (texts / "skill.md").read_text(encoding="utf-8")
        for command_name in SKILLS:
            text = text.replace(f"/coloqo:{command_name}", f"{prefix}coloqo-{command_name}")
        return text.replace("Claude Code session", "session")
    source = (texts / f"{name}.md").read_text(encoding="utf-8")
    _, front, body = source.split("---", 2)
    description = next(
        line.split(":", 1)[1].strip()
        for line in front.splitlines()
        if line.startswith("description:")
    )
    body = body.strip().replace("$ARGUMENTS", "the text the user wrote after the skill's name")
    return f"---\nname: coloqo-{name}\ndescription: {description}\n---\n\n{body}\n"


def write_skills(agent: Agent) -> list[Path]:
    """Write the three skills into the user's skills folder and return their files.

    Args:
        agent: The agent.

    Raises:
        InstallError: A skill cannot be written.
    """
    written = []
    for name in ("coloqo", *SKILLS):
        folder = skills_home() / (name if name == "coloqo" else f"coloqo-{name}")
        path = folder / "SKILL.md"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(skill_text(name, agent), encoding="utf-8")
        except OSError as error:
            raise InstallError(f"Cannot write {path}: {error}") from error
        written.append(path)
    return written


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one of the agent's own commands.

    Args:
        args: The command and its arguments.

    Raises:
        InstallError: The command is not found.
    """
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as error:
        raise InstallError(f"`{args[0]}` is not found: is the agent installed?") from error
    except subprocess.SubprocessError as error:
        raise InstallError(f"`{' '.join(args)}` failed: {error}") from error


def install_codex() -> list[str]:
    """Write Coloqo's hooks, MCP server and skills for Codex; return what was done.

    The MCP server goes through Codex's own ``codex mcp add``, which keeps its settings' format.

    Raises:
        InstallError: A file cannot be changed, or ``codex`` failed.
    """
    path = codex_home() / "hooks.json"
    _write_json(path, merge_hooks(_read_json(path), Agent.Codex))
    _run(["codex", "mcp", "remove", "coloqo"])
    args = command(Agent.Codex, "mcp").split()
    added = _run(["codex", "mcp", "add", "coloqo", "--", *args])
    if added.returncode != 0:
        raise InstallError(f"`codex mcp add` failed: {added.stderr.strip() or added.stdout}")
    skills = write_skills(Agent.Codex)
    return [
        f"hooks: {path}",
        f"MCP server `coloqo`: {' '.join(args)} (codex mcp add)",
        f"skills: {', '.join(str(p.parent) for p in skills)}",
    ]


def install_qwen() -> list[str]:
    """Write Coloqo's hooks, MCP server and skills for Qwen Code; return what was done.

    Hooks and the MCP server both live in Qwen's user settings, written in one go.

    Raises:
        InstallError: A file cannot be changed.
    """
    path = qwen_settings()
    settings = merge_hooks(_read_json(path), Agent.Qwen)
    servers = settings.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise InstallError(f"`mcpServers` in {path} is not an object; fix it by hand first")
    args = command(Agent.Qwen, "mcp").split()
    servers["coloqo"] = {"command": args[0], "args": args[1:]}
    _write_json(path, settings)
    skills = write_skills(Agent.Qwen)
    return [
        f"hooks and MCP server `coloqo`: {path}",
        f"skills: {', '.join(str(p.parent) for p in skills)}",
    ]


def install(agent: Agent) -> list[str]:
    """Install Coloqo for the agent and return the lines to show the user, next steps included.

    Args:
        agent: ``codex`` or ``qwen``.

    Raises:
        InstallError: The agent is Claude Code, which takes the plugin, or a step failed.
    """
    if agent is Agent.Claude:
        raise InstallError(
            "Claude Code takes the plugin: `/plugin install coloqo --marketplace coloqo/coloqo`"
        )
    done = install_codex() if agent is Agent.Codex else install_qwen()
    lines = [f"Coloqo {__version__} for {agent}:", *(f"- {line}" for line in done), ""]
    lines.append("Next:")
    if not load_token(server_url()):
        lines.append("- log this computer in: `uvx coloqo login`")
    approve = "the hooks" if agent is Agent.Codex else "the hooks and the MCP server"
    lines.append(f"- start {agent}, approve {approve} it asks about (`/hooks`), then restart it;")
    lines.append(
        "- new messages reach a session at the next prompt; link a project with "
        f"{'$' if agent is Agent.Codex else '/'}coloqo-link."
    )
    return lines
