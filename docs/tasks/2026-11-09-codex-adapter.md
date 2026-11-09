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

   **Answer (author, 2026-11-09): an installer**, one for both agents: `uvx coloqo install --agent
   codex|qwen` writes, once per computer and at the user level, the hooks (`~/.codex/hooks.json`;
   `hooks` in `~/.qwen/settings.json`), the MCP server (`~/.codex/config.toml`; `mcpServers` in
   `~/.qwen/settings.json`) and the skill (`~/.agents/skills/coloqo`, read by both). Neither agent's
   plugins carry hooks today: Codex's docs contradict each other on plugin hooks in the CLI, and
   Qwen's extensions list no hooks; without hooks there is no briefing and no Inbox reminder. A
   plugin may replace the installer once its hooks work. **The functionality is to be checked on
   both Codex and Qwen** (the author).
2. **Liveness of a Codex session** (decision 0029): live for a while after its last hook call, or a
   detached `watch` started by the session start hook?

   **Answer (author, 2026-11-09): a heartbeat from the MCP server, with "a minute after a request"
   as the fallback.** The agent starts Coloqo's MCP server per session and it dies with the
   session (its stdin closes), so a background thread there calls the server every 15 s with no
   orphaned process. It needs the MCP server to know its session id — to check by running (Qwen
   may give `QWEN_CODE_SESSION_ID`; Codex's hook environment had none). Without it, decision 0029's
   rule already applies: the prompt hook asks `/inbox` at each prompt and the tools call the
   server, so a session is online for a minute after each; a Message to it while it is offline
   goes to its person and shows at the next prompt. Not taken: a detached `watch` started by the
   SessionStart hook — unverified under the agents' sandboxes, and a session killed without
   SessionEnd would stay "online" for good, its Messages going to a dead session.
3. **Which agent drives the plugin**: told by the installer (an argument in each hook command) or
   detected from the environment?

   **Answer (author, 2026-11-09): told by the installer.** It adds `--agent codex` or `--agent qwen`
   to each hook command and to the MCP server's arguments; without the flag the agent is Claude
   Code, so the Claude Code plugin and its pins work as before. The plugin sends the agent to the
   server in a header beside its version, so the update hint (decision 0027) names that agent's
   commands. The environment is read only within the agent already known (Qwen's session id from
   `QWEN_CODE_SESSION_ID`). Not taken: detecting the agent — Codex's hook environment has nothing of
   its own, and guessing from input fields (`turn_id`, `model`) breaks with the agent's versions.
4. **Commands `/coloqo:focus` and `/coloqo:link`** in Codex: skills of their own, or only through
   the main skill and the tools (`set_focus`, `link_project`)?

   **Answer (author, 2026-11-09): two small skills, `coloqo-focus` and `coloqo-link`**, installed
   beside the main one in `~/.agents/skills`, with the text of the Claude Code commands and made
   from the same source; invoked as `$coloqo-focus quiet` in Codex, `/coloqo-focus quiet` in Qwen,
   and listed by `/skills`. Their narrow descriptions keep them from firing unasked. Not taken: only
   the main skill and words — a member would learn of the focus only if told.
5. **Updates** (decision 0027) for Codex: the hint tells the assistant to run the installer with the
   new version — enough?

   **Answer (author, 2026-11-09): try a pinned version in every command, re-approved after each
   update.** The hint names the installer with the new version (`uvx coloqo@<new> install --agent
   codex`), then "approve the changed hooks in `/hooks` and restart the session". A changed command
   line is a changed hook definition, so each update likely asks for approval again — to confirm on
   the pilot. Nothing is worked around: the user sees the hooks changed, within the agent's own
   trust mechanism. The alternative, kept for the case the re-approvals prove painful: a fixed
   command line calling a wrapper whose version lives in a file the installer rewrites — changing a
   script does not revoke approval, so updates would pass silently, but that sidesteps the very
   check the agent has. "Let's try (a)" — revisited after the pilot if needed.

   **The update path is checked on purpose, not learned from bugs** (author, 2026-11-09: "so that
   we control updates rather than catch bugs"). Before newcomers install, and again for every
   release that changes what the installer writes: install version N, then N+1 by the hint's own
   command; see whether the agent asks to approve the hooks again; after approving and a restart,
   the hooks and the MCP server run N+1 (the server sees N+1 in the header) and nothing of N is
   left in the settings. A failure here blocks the rollout.

   **Run from within the session** (a side review, 2026-11-09): the installer rewrites files in
   `~/.codex` and `~/.qwen`, outside the project, while Codex runs in `workspace-write` and may refuse
   or ask; item 8 was checked with `bump.sh` from a plain terminal, not by the Assistant. So the
   hint has the Assistant run the command and, if the sandbox refuses, ask its user to run it in a
   terminal; the pilot runs the update by the hint's command from within a Codex and a Qwen session.
6. **Pilot**: who checks it first and against what — the team's new member, before they start on
   tasks.

   **Answer (author, 2026-11-09): two steps.**
   - **The author first**, on their machine, in both Codex and Qwen, against a test Team on
     `app.coloqo.team`: (1) the installer writes the hooks and the MCP server, the hooks approved in
     `/hooks`; (2) the briefing at session start; (3) the Inbox reminder at a prompt with an
     addressed Message; (4) the tools: `read_topic`, `post_message`, `take_task`, `change_stage`;
     (5) the trail on file edits — `Bash` and `apply_patch` in Codex, `write_file` and `edit` in
     Qwen, with `apply_patch`'s name confirmed; (6) the MCP server knows its session and keeps the
     heartbeat, or the minute rule holds; (7) the skills `coloqo-link` and `coloqo-focus`; (8) the
     update path from N to N+1 as above, by the hint's command run by the Assistant from within
     the session, and by the user in a terminal when the sandbox refuses; (9) the network from hooks and the MCP server under the
     agent's sandbox.
   - **Then the team's newcomers**, on their first day before any task, one in Codex and one in
     Qwen, with the author or the lead: the install, the briefing and one test Topic on their own
     machines, so that what breaks only there (Windows, a proxy, the sandbox) is fixed before work.
   - Items 5, 6 and 9 are checked **before the code**, with test hooks as on 2026-11-09: item 6
     decides how the heartbeat is built (answer 2).

## Settled (2026-11-09)

- `uvx coloqo install --agent codex|qwen` writes, at the user level, the hooks, the MCP server and
  three skills (`coloqo`, `coloqo-focus`, `coloqo-link` in `~/.agents/skills`); a plugin may
  replace it once the agents' plugins carry hooks.
- The agent is told by `--agent` in each hook command and the MCP server's arguments; none means
  Claude Code. The plugin sends it to the server beside its version.
- Liveness: a heartbeat from the MCP server if it learns its session; otherwise decision 0029's
  minute after a request.
- Delivery: the Inbox and new Messages reach a Codex or Qwen session at the next prompt; no monitor.
- Updates: the hint names the installer with the new version, then approving the hooks and a
  restart; the update path is checked on purpose before each rollout.
- Pilot: the author in both agents first, by the list above; then the newcomers before their tasks.

## Checked by running (2026-11-09, Codex 0.160, Qwen Code 0.27.1)

Sandbox projects with a logging test hook; hooks approved by the author by hand.

- **The SessionStart hook's plain stdout reaches the model** — in both.
- **Changing the hook's script does not revoke the approval** — in both: Codex keeps a hash of the
  hook's definition (`[hooks.state."<hooks.json path>:<event>:i:j"] trusted_hash` in
  `config.toml`), Qwen a hash of the config (`~/.qwen/hookApprovals.json`). A changed command line
  (a new pinned version) is a changed definition — not run, expected to ask again.
- **Hook input, Codex**: `session_id`, `cwd`, `transcript_path`, `model`, `permission_mode`; tool
  events add `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, `turn_id`. The shell shows
  as `Bash` with `command`, as in Claude Code. No session id in the hook's environment.
- **Hook input, Qwen**: the same fields plus `timestamp`, `prompt_id`; the environment carries
  `QWEN_CODE_SESSION_ID` and `QWEN_PROJECT_DIR`, the analogues of Claude Code's. A file write is
  `write_file` with `file_path`.
- Not checked: the name of `apply_patch` in a Codex hook's input (the nested sandbox failed to write
  in the test), the MCP server's knowledge of its session, network under the agents' sandboxes.

## Checked by running, second pass (2026-11-09 evening, Codex 0.160.0, Qwen Code 0.27.1)

A probe (one stdlib script acting as a hook and as a stdio MCP server, logging all it sees) in two
sandbox projects, run by the author from a plain terminal; the MCP server given to Codex with
`-c mcp_servers…` at launch, so `~/.codex/config.toml` stayed unchanged.

- **The MCP server learns its session — in both.** Qwen puts `QWEN_CODE_SESSION_ID` into the MCP
  server's environment at start, equal to the hooks' `session_id`. Codex puts nothing into its
  environment, but every `tools/call` carries `_meta.sessionId` (and
  `_meta["x-codex-turn-metadata"].session_id`) equal to the hooks' `session_id`; and the hooks and
  the MCP server share their parent process (`codex`, `node` for Qwen), so a hook can leave the
  session id under the agent's pid for the MCP server to read before any tool call. The heartbeat
  from the MCP server (answer 2) is possible in both.
- **The MCP server dies with the session — in both**: Qwen closes its stdin, Codex kills it; no
  process was left.
- **Network — in both**: hooks and the MCP server got HTTP 200 from `app.coloqo.team`; Codex ran in
  `workspace-write`.
- **Tools seen by PostToolUse.** Qwen: `write_file` (`file_path`, `content`), `run_shell_command`
  (`command`, `description`), MCP tools as `mcp__<server>__<tool>`. Codex: `Bash` (`command`),
  MCP tools as `mcp__<server>__<tool>`. Asked to, both edited a file with their own tool: Codex's
  `apply_patch` comes with one argument, `command`, holding the patch text — the paths are in its
  `*** Update File: <path>` (and `Add File`, `Delete File`) lines, absolute here; Qwen's `edit`
  comes with `file_path`, `old_string`, `new_string`, like Claude Code's `Edit`. Qwen also showed
  `read_file` (`file_path`) and `tool_search` (`query`).
- **A changed hook command asks for approval again — in both** (a `-B` added to every command, as
  a new pinned version would). The author: "one question after an update, looks acceptable, not a
  bother". Answer 5 holds.
- **Traps for the code.** Qwen's `QWEN_CODE_PROJECT_DIR` is Qwen's own storage
  (`~/.qwen/projects/…`), not the project; the project is `QWEN_PROJECT_DIR`, which hooks see and the
  MCP server does not (it has `cwd`). Codex fires SessionStart at the first prompt, not at launch,
  while its MCP server starts at launch: the briefing comes with the first prompt.

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
