# 0035. Coloqo in Codex and Qwen Code

**Date:** 2026-11-09 · **Question:** members of the prototype team who work in Codex or Qwen Code
get nothing from Coloqo, whose way of working rests on the Claude Code plugin · **Refines:**
decisions 0006, 0011, 0024, 0027, 0029

On 2026-11-09 new members joined the prototype team; each developer picks their own tools, and two
newcomers work in Codex and in Qwen Code. Decision 0011 planned this: "the adapter for an agent is
configuration, not code", with the input hook as the portable basis of delivery (decision 0006).
The working file is `docs/tasks/2026-11-09-codex-adapter.md`; its facts come from both agents'
documentation and from two probes run on 2026-11-09 (Codex 0.160.0, Qwen Code 0.27.1).

## Decision

**An installer, one for both agents**: `uvx coloqo install --agent codex|qwen` writes, once per
computer and at the user level, so it works in every project:

- the hooks: SessionStart, UserPromptSubmit, PostToolUse, Stop — into `~/.codex/hooks.json`, or
  the `hooks` of `~/.qwen/settings.json`, each command pinned to `uvx coloqo@<version>`, as the
  Claude Code plugin pins them; entries of other tools are kept;
- the MCP server: through Codex's own `codex mcp add`, which keeps its settings' format; into
  the `mcpServers` of Qwen's settings, in the same write as the hooks;
- three skills into `~/.agents/skills`, which both agents read: `coloqo`, and `coloqo-focus` and
  `coloqo-link` made from the Claude Code commands `/coloqo:focus` and `/coloqo:link`; invoked as
  `$coloqo-focus` in Codex and `/coloqo-focus` in Qwen.

The user approves the hooks once in the agent's `/hooks`. Neither agent's plugins carry hooks today
(Codex's documentation contradicts itself on plugin hooks in the CLI; Qwen's extensions list no
hooks), and without hooks there is no briefing and no Inbox reminder. A plugin may replace the
installer once its hooks work.

**The agent is told, not guessed**: the installer adds `--agent codex` or `--agent qwen` to each
hook command and to the MCP server's arguments; without the flag the agent is Claude Code, so the
Claude Code plugin and its pins work as before. By it the plugin picks the session id, the project
directory and the tool names, and it sends the agent to the server in `X-Coloqo-Agent`, beside
`X-Coloqo-Plugin`.

- The session: Qwen gives `QWEN_CODE_SESSION_ID` to hooks and the MCP server alike. Codex gives the
  hooks `session_id` in their input, and the MCP server `_meta.sessionId` with each tool call; its
  hooks leave the session id under the pid of the `codex` process they share with the MCP server,
  so the MCP server knows the session before its first tool call.
- The project: `QWEN_PROJECT_DIR` in Qwen's hooks (not `QWEN_CODE_PROJECT_DIR`, which is Qwen's own
  storage), the hook input's `cwd` in Codex; the MCP server's working directory in both.
- The trail (decision 0023) knows each agent's tools: Codex's `apply_patch`, whose one argument
  holds the patch with its `*** Update File: <path>` lines, and `Bash`; Qwen's `edit` and
  `write_file` (`file_path`) and `run_shell_command`.

**The web shows each session's agent** (the author, 2026-11-09): the server keeps the agent an
Assistant last registered with, and the Team page and the person's own sessions show it as an icon
beside the session's name — the agents' own icons, chosen by the author — with the agent's name
on hover; beside a written name the icon is decoration, hidden from assistive technology. The hint
with a session's id names the command that resumes it where the agent has one (`claude --resume`,
`codex resume`).

**Liveness is a heartbeat from the MCP server** (decision 0029). The agent starts the MCP server for
the session and ends it with the session, so a thread in it tells the server every 15 s that the
session runs and posts the intervals of whose move it was (decision 0033), as `watch` does in Claude
Code. Until the MCP server knows its session, decision 0029's rule applies: a session that made a
request within the last minute is online, and the prompt hook makes one at each prompt.

**Delivery comes at the next prompt**: there is no monitor in either agent, so the Inbox and new
Messages reach a session by its prompt hook (decision 0006), not by themselves. Codex runs its
SessionStart hooks at the first prompt, so the briefing comes with it.

**Updates** (decision 0027): the hint names the installer with the new version for the session's
agent. The Assistant runs it; if the agent's sandbox stops it (a shell command without network, or the
agent's settings outside the project), it asks its user to run the same command in a terminal. Then the user approves the changed hooks in
`/hooks` — a new pinned version is a changed hook definition, and both agents ask again — and
restarts the session. The author found one approval per update acceptable (2026-11-09). The update
path is checked on purpose before each rollout that changes what the installer writes: version N,
then N+1 by the hint's own command run from within a session, then the hooks and the MCP server on
N+1 with nothing of N left; a failure blocks the rollout.

**The pilot**: the author first, in both agents, against a test Team, by the list in the working
file; then the team's newcomers on their first day before any task.

## Why

- An installer reaches both agents today with one mechanism; waiting for plugin hooks would leave
  the newcomers without Coloqo for an unknown time.
- An explicit agent costs the installer nothing and cannot be mistaken; Codex's hook environment
  has nothing of its own to detect it by.
- The MCP server lives exactly as long as the session, so its heartbeat leaves no orphan. A
  detached `watch` started by a hook was not taken: a session killed without SessionEnd would stay
  "online" for good, its Messages going to a dead session.
- A pinned version re-approved after each update stays within the agent's own trust mechanism. A
  fixed command line reading its version from a file would pass updates silently, but it sidesteps
  the very check the agent has; it is kept as the way back if re-approvals prove painful.

## Not decided here

- The timeout of Qwen's hooks: the installer leaves Qwen's default until the pilot shows it.
- Windows: the pid shared by Codex's hooks and MCP server is found through `/proc` or `ps`; on
  Windows the Codex MCP server learns its session at the first tool call.
