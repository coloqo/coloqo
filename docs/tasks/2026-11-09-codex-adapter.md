# Coloqo for members who work in Codex or Qwen Code

## What happened

2026-11-09, the prototype team. New members are joining the team, and they do not use Claude Code:
each developer picks their own tools, and Codex is a new member's personal choice (the lead). The
team's whole way of working with Coloqo rests on the Claude Code plugin: the session start
briefing, the Inbox reminder on each prompt, the trail of visible work, the monitor that brings
events without asking. A member in Codex today gets none of it: their assistant sees no tasks
and no Topics, receives nothing and leaves no trail.

Decision 0011 already planned this: "the adapter for an agent is configuration, not code"; Codex
CLI was named among the later agents, and the portable basis of delivery is the reminder through
the input hook (decision 0006), with the monitor as an improvement where it exists.

The same day the team settled how its shared agent rules reach Codex (outside Coloqo): a block
generated into the home project's `AGENTS.md` and refreshed by a SessionStart hook. That work needs
trusted projects and reviewed hooks in Codex, the same as here.

## Facts checked (2026-11-09)

Codex — from the OpenAI documentation (learn.chatgpt.com/codex, Codex CLI 0.167.0 of 2026-11-06).
The author has `codex-cli 0.160.0` installed; nothing below has been run yet.

- **Hooks exist and are on by default**: SessionStart, SessionEnd, UserPromptSubmit, PreToolUse,
  PostToolUse, Stop and more; handlers `command` and `mcp_tool`. Config — `hooks.json` with a
  top-level `hooks` object, or `[[hooks.<Event>]]` in `config.toml`; places — `~/.codex/` and a
  project's `.codex/`. A Windows variant of the command — `commandWindows`.
- **What reaches the model**: plain stdout of SessionStart and UserPromptSubmit becomes developer
  context; JSON `additionalContext` works for SessionStart, UserPromptSubmit, SubagentStart and
  PostToolUse. A large value is spilled to a file with a preview of about 2,500 tokens. Plain
  stdout of PostToolUse is ignored — our PostToolUse already answers in JSON.
- **Hooks must be trusted**: a new or changed non-managed hook is skipped until the user reviews it
  in `/hooks`; a project's `.codex/` layer loads only when the project is trusted.
- **MCP** — `[mcp_servers.<name>]` in `~/.codex/config.toml` (`command`, `args`, `env`), or
  `codex mcp add`.
- **Skills** — the same `SKILL.md` format; searched in `.agents/skills` of the project and in
  `~/.agents/skills`; invoked by `$name` or `/skills`, or implicitly by description.
- **Plugins exist** (`plugin.json` of agent-plugins.org, `skills/`, `mcp.json`, hooks in
  `hooks/hooks.json`; marketplaces in `.agents/plugins/marketplace.json`). The docs contradict each
  other on hooks: the packaging page says plugin hooks are for "manually installed Codex desktop
  plugins only", the hooks page loads plugin hooks with the others. For the CLI — unconfirmed; the
  docs also say installing and testing plugins happens in the desktop app.
- **No monitor**: nothing in the interactive CLI brings a background command's lines to the model
  as notifications. `codex exec --json` and the app server stream events to a client, not to the
  model.
- **The plugin assumes Claude Code in a few places**: the session id comes from
  `CLAUDE_CODE_SESSION_ID` (`focus.py`) and the project from `CLAUDE_PROJECT_DIR` (`hooks.py`, with
  `cwd` from the hook input as a fallback); the trail matches the tool names `Edit`, `Write`,
  `MultiEdit`, `NotebookEdit`, `Bash`, `PowerShell` and their argument names (`file_path`,
  `command`). The Codex docs' own example matches `^Bash$`; a file edit in Codex is `apply_patch` —
  what names and arguments the hooks actually see is not checked. `/coloqo:focus` and
  `/coloqo:link` are Claude Code commands. The update hint of decision 0027 names
  `claude plugin …` commands.
- **Liveness rests on `watch`** (decision 0029): its heartbeat every 15 s is how the server knows a
  session runs and whom an address reaches. A Codex session without a monitor has no `watch`.

## Qwen Code too (added 2026-11-09)

A second new member will work in Qwen Code on Linux. From the docs in the QwenLM/qwen-code
repository (`docs/users`, CLI 0.27.1 of 2026-11-09); not installed, not run. It stands much closer
to Claude Code than Codex does:

- **Hooks** — the same events in the `hooks` key of `settings.json` (`~/.qwen/`, `.qwen/`); the
  input carries `session_id`, `cwd`, `tool_name`, `tool_input`; matchers accept Claude Code names
  (`Bash`, `Write`) besides its own ids (`run_shell_command`, `write_file`, `edit`); plain stdout of
  SessionStart and UserPromptSubmit reaches the model, JSON `additionalContext` too. User hooks load
  regardless of folder trust; project hooks wait for an approval tied to the exact config.
- **MCP** — `mcpServers` in `settings.json`, the same shape as Claude Code; `qwen mcp add`.
- **Skills** — `SKILL.md` in `~/.qwen/skills` or `~/.agents/skills` (shared with Codex), project
  `.qwen/skills`, `.agents/skills`; `/<skill>` invokes one.
- **Extensions** install from git, npm or a marketplace and accept a Claude Code plugin's manifest,
  but no hooks are listed among an extension's fields. No monitor.

So the Qwen adapter may be almost pure configuration: the same `hook` commands in
`~/.qwen/settings.json`, the same MCP entry, the skill. Its open points are the same as Codex's:
liveness without `watch`, the session id for the MCP server, the update hint.

## Proposal (to discuss)

1. **An installer, not a plugin, for now**: `uvx coloqo install --agent codex` writes, once per
   computer, the hooks into `~/.codex/hooks.json` and the MCP server into `~/.codex/config.toml`,
   pinned to `uvx coloqo@<version>` like the Claude Code plugin, and the skill into
   `~/.agents/skills/coloqo`. User-level, so it works in every project, as the plugin does. The user
   reviews the hooks once in `/hooks`. When plugin hooks are confirmed in the CLI, a Codex plugin
   replaces the installer.
2. **Delivery by the prompt hook**: the Inbox and new messages reach a Codex session at the next
   prompt (decision 0006), not by themselves. Said plainly in the install text.
3. **The plugin learns which agent drives it**: a hook argument or an environment variable set by
   the installer; it picks the session id, the project, the tool names and the update commands for
   that agent. The plugin sends it to the server, so the update hint of decision 0027 names the
   right commands (for Codex — run the installer again).
4. **Liveness without a monitor** — one of: the session counts as live for some minutes after its
   last hook call; or the SessionStart hook starts a detached `coloqo watch` for the session, which
   keeps the heartbeat and the local cache the prompt hook already asks (decision 0011), and
   SessionEnd stops it.

## Questions, one at a time

1. **Form of delivery**: an installer writing user-level Codex settings now, a Codex plugin later —
   or wait for plugin hooks in the CLI?
2. **Liveness of a Codex session** (decision 0029): live for a while after its last hook call, or a
   detached `watch` started by the session start hook?
3. **Which agent drives the plugin**: told by the installer (an argument in each hook command) or
   detected from the environment?
4. **Commands `/coloqo:focus` and `/coloqo:link`** in Codex: skills of their own, or only through
   the main skill and the tools (`set_focus`, `link_project`)?
5. **Updates** (decision 0027) for Codex: the hint tells the assistant to run the installer with the
   new version — enough?
6. **Pilot**: who checks it first and against what — the team's new member, before they start on
   tasks.

## To check by running Codex before the code

- The hook input: `session_id`, `cwd`, `tool_name`, `tool_input` and their names for the shell and
  for `apply_patch`.
- Whether the MCP server started by Codex can learn the session it serves (the session id in its
  environment or in the request), as decision 0024 needs.
- Whether hooks and the MCP server reach the network under Codex's sandbox, and whether a detached
  process started by a hook outlives it.
- Whether changing the pinned version in `hooks.json` makes the hooks untrusted again until
  reviewed — then every plugin update asks the user once more.
- The plain stdout of SessionStart: the briefing stays well under the 2,500-token preview.
