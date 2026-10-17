# Coloqo analogs: market review

**Review date:** 2026-10-15.

**Method.** Web search (standard and extended modes), then reading primary sources:
repository READMEs, official vendor documentation and announcements, protocol specifications.
We searched in four directions:
1. Services and open projects for communication between agents of different people on one team:
   "agent mail", "agent-to-agent messaging", MCP servers for agent communication, relays
   between machines.
2. Capabilities of the major players: Claude Code, OpenAI Codex, GitHub Agent HQ, Cursor, Devin,
   Factory, Slack, Microsoft Teams and Copilot Studio, Atlassian Rovo, GitLab Duo.
3. Protocols: A2A, MCP, IBM ACP, AGNTCY, ANP.
4. Multi-agent frameworks, for contrast only.

**Freshness caveat.** The field changes month by month. Stars and versions were taken on 2026-10-15.
For many repositories the page does not show the date of the last commit. Claims from
secondary sources are marked. A missing feature in this review means "not found", not
"does not exist" (see the section "What was not confirmed").

## Summary

- **There is no direct mature competitor.** Closest by model is Coopagents: "each person
  joins with their own agent and their own account", a shared task board, actions reserved
  for humans are hidden from agents. But it is an alpha with one star and no recording of the outcome in the tracker.
- **The major players solve adjacent problems.** Claude Code (agent teams, messaging
  between sessions) connects the agents of **one** person. Claude Tag, OpenAI workspace agents
  and Rovo provide a **shared organization agent**, not a representative of each member.
- **Agents of different people negotiating with each other: we did not find this at the major vendors.**
  A request for it has been open in the Claude Code repository since 2026-02-24 (issue #28300), with no
  answer from Anthropic there.
- **Overlaps with open projects.** Transport and mailboxes (MCP Agent Mail,
  hoptell, agent-talk), threads and human oversight (HumanOverseer in Agent Mail, Matrix rooms
  in AgentTeams). Rovo, Devin, Agent HQ and GitLab Duo write to the tracker, but there
  the agent executes a task rather than taking part in the discussion before code.
- **The combination of three things is unique:** an assistant (a person's representative) with that person's rights;
  a channel tied to a tracker issue that lives while the issue is relevant; mandatory
  recording of the outcome in an MR or an issue.
- **What to reuse:** the A2A data model (Task, contextId, input-required, Artifact)
  as a format; MCP as the way to connect; Channels in Claude Code for inbox delivery.
  Ideas: from Agent Mail — thread_id = issue key, archive in git, HumanOverseer; from Coopagents —
  actions reserved for humans kept out of the agent's tools; from Claude Code — the rule "a message
  from an agent does not equal a human's consent".

## Candidate table

### 1. Coordination of agents of different people and communication between agents

| Candidate | What it is | Maturity | Assistant (a person's representative) | Task channels / oversight / outcome recording | Connection | Link |
|---|---|---|---|---|---|---|
| MCP Agent Mail (Python) | "Mail" for coding agents: agent names, mailboxes, searchable threads, advisory file locks; messages are stored as markdown files in git, search is SQLite FTS5 | OSS. About 2.2k stars. The README says the version is "no longer maintained", new users are pointed to the Rust port | No. An agent registers in a project under a name like "GreenCastle". A multi-user model (several people) is not described in the README | Threads exist (`thread_id`); they recommend using the Beads issue key as `thread_id`. Oversight: the `/mail` web interface and messages from `HumanOverseer` that bypass the contact policy. Writing to an MR is not described; there is a pre-commit hook for locks | MCP (Streamable HTTP, stdio), port 8765 | [github](https://github.com/Dicklesworthstone/mcp_agent_mail) |
| MCP Agent Mail (Rust) | A Rust rewrite of the same: about 40 tools, TUI, web interface | OSS, active. 200 stars. v0.3.31 and v0.3.39 are mentioned; the page does not show the date of the last release. License "MIT+Rider" | No. Binding identity to a session is mentioned starting with v0.3.39 | Threads, a web interface "for human review and oversight", HumanOverseer, a Beads link (`[br-123]` in the subject) | MCP (stdio, HTTP) | [github](https://github.com/Dicklesworthstone/mcp_agent_mail_rust) |
| Coopagents (formerly Crewmesh) | "Multiplayer mode" for Claude Code and Codex: a shared task board for the team's agents, questions to the task owner, handoff of work | OSS, MIT. Alpha (0.7.0rc2), 1 star. Tested only on a few configurations | **Yes.** "Each person joins with their own agent and their own account"; actions available only to humans are not in the MCP tool list | Task board, task claim — only one agent wins. Requests to the owner go through statuses (read, in progress, answered, resolved). Humans approve "contracts" and handoffs, revoke members. No per-task channel and no tracker recording | MCP. P2P via iroh, the space lives on the creator's machine, the relay sees only ciphertext | [github](https://github.com/Weichenleeeee123/coopagents) |
| agent-talk (on top of retalk) | A plugin: an agent writes to agents of other people and organizations through an end-to-end encrypted relay | OSS, MIT. 192 stars. The code "has not been independently audited" | Partly. Identity is a key; a peer is added by fingerprint or invitation. No "human is the owner" model | No task channels. Agents send and receive on their own; the authors recommend auto permission mode. There is only sender blocking and key verification. No outcome recording | Plugin and CLI, public or self-hosted relay | [github](https://github.com/xhluca/agent-talk) |
| hoptell | Its own WebSocket relay: agents in different sessions, tools and machines write to each other; an incoming message wakes an idle agent | OSS, Apache-2.0. 8 stars | Partly. A member has their own token, agent names start with the member's name. Roles (`@reviewer`) are routing, not rights | Addressing by name, role or `@all`. The agent is told that a message is from an agent rather than from the user, but this is "guidance for the model, not a sandbox". No tracker recording | MCP, CLI, tmux wrapper. No TLS, VPN recommended | [github](https://github.com/EminUZUN/hoptell) |
| Concord MCP | A local coordination layer: tasks with a lifecycle, file claims, handoff of work, decisions and findings attached to a task, review packets | OSS, MIT. 515 stars, no releases | No. Agents of one local checkout, "not a hosted sync service" | Decisions and findings are tied to a task; the recipient must accept a handoff; generates `HANDOFF.md` and `REVIEW_PACKET.md`. Oversight is a read-only dashboard. No tracker integration | MCP (npm), five tools | [github](https://github.com/Get-Concord-AI/concord-mcp) |
| agent-comm | Channels, direct and broadcast messages, a shared key-value store, a dashboard | OSS, MIT. 9 stars | No | Channels exist. Hooks block editing another agent's file. No manual human approval and no tracker | MCP (stdio), REST, WebSocket. Loopback only by default | [github](https://github.com/keshrath/agent-comm) |
| mcp-coordinator | An MQTT broker plus MCP. An agent announces files; a conflict opens a "consultation thread" | OSS, MIT. 1 star, 658 commits | Partly. Scenario "small team where everyone runs their own AI agent", JWT or OAuth 2.1 | Consultation threads, agents negotiate on their own. No human approval gate, there is a dashboard. No tracker recording | MCP (HTTP or stdio), MQTT | [github](https://github.com/swoofer/mcp-coordinator) |
| Agent Communication MCP (mkXultra) | Slack-style rooms, @-mentions, presence | OSS, MIT. No date | No | Rooms "by topic or by team". Oversight not described | MCP. File mode or cloud mode (via a token) | [glama](https://glama.ai/mcp/servers/mkXultra/agent-communication-mcp) |
| RelayRoom | A self-hosted hub: a message board with threads per "part" of the system | Open core: hub AGPL-3.0, CLI Apache-2.0. Price not stated | No. "You talk to one agent. It talks to the rest", one owner | Threads have statuses (open, answered, holding, closed). A live dashboard, a human can intervene. Agents open PRs, no tracker | MCP | [relayroom.dev](https://relayroom.dev/) |
| AgentDM | A messaging service for agents: address book, mailboxes, channels, binding a channel to Slack | Service. Post dated 2026-04-10, version v1.1 | Not described. There are teams and accounts | Channels. A human reads the agents' conversation in Slack and intervenes. No tracker recording | "Any MCP compatible agent" | [agentdm.ai](https://agentdm.ai/blog/humans-in-slack-talking-to-agentdm-agents) |
| AgentTeams (agentscope-ai) | A multi-agent "OS": Manager and Workers in containers, communication in Matrix rooms | OSS, Apache-2.0. About 5.8k stars, v1.2.4 of 2026-09-20 (from the News section) | No. Workers are the team's executors | "Every Matrix room includes you, the Manager, and the relevant Workers", "No hidden agent-to-agent calls". The outcome is a link to a PR | Matrix. MCP is used for tools; how to connect an external Claude Code is not described | [github](https://github.com/agentscope-ai/AgentTeams) |
| Coral Protocol | Agent threads on top of MCP, a thread is tied to a task | Early stage: remote mode "in active development" | No | A thread per task with participants and history. Oversight and tracker not described | MCP | [docs](https://docs.coralprotocol.org/gettingstarted) |

### 2. Major players

| Candidate | What it is | Maturity | Assistant (a person's representative) | Task channels / oversight / outcome recording | Connection | Link |
|---|---|---|---|---|---|---|
| Claude Code: agent teams | A lead session launches "teammates": a shared task list, mailboxes, direct messages between agents | Experimental, off by default (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) | No. All teammates are instances of one person: "One team per session", mailboxes are JSON files in `~/.claude/teams/` | Task list with statuses. The human sees and writes to any teammate. Hooks `TaskCompleted` and others. No tracker recording | Built in | [docs](https://code.claude.com/docs/en/agent-teams) |
| Claude Code: cross-session messaging | A session writes to another session of the same person: on this machine, on other machines or in the cloud | Enabled since v2.1.224 (macOS, Linux) | No. Only "your other Claude Code sessions"; across machines — via Remote Control of the same account | No channels, text only. Important semantics: a message from another session "never counts as your consent"; incoming messages can be accepted, held or refused | Built in (`SendMessage`, `ListAgents`) | [docs](https://code.claude.com/docs/en/cross-session-messaging) |
| Claude Code: Channels | An MCP server pushes events into an already open session, two-way, with forwarding of permission requests | Research preview. In Team and Enterprise an administrator enables it | Not applicable, it is a delivery mechanism | Not applicable. Caveat in the docs: Claude Code "doesn't register a channel server that negotiates protocol revision 2026-07-28" | MCP (plugin, `--channels`) | [docs](https://code.claude.com/docs/en/channels) |
| Claude Tag (Slack) | @Claude in Slack channels: multi-step work, a reply in the thread, "ambient" mode | Beta since 2026-06-23 for Team and Enterprise. Replaces the former Claude in Slack | No. "There's one Claude that interacts with everyone" — a shared organization identity per channel | Work in the channel thread. A log of "everything @Claude has done and who requested each task", per-channel limits. Tracker recording via connected tools, not described separately | Slack, connectors | [announcement](https://www.anthropic.com/news/introducing-claude-tag), [Claude Code in Slack](https://code.claude.com/docs/en/slack) |
| OpenAI: ChatGPT/Codex in Slack | @ChatGPT in a channel hands repository work to a Codex cloud task; the result comes back to the thread | Integration GA 2025-10-06 | Partly. The task is on the requester's account; a reply in the channel "doesn't give every channel member access to the underlying task" | Slack thread. Only the same account can continue. PR creation is not described on the page | Slack, Codex cloud | [docs](https://learn.chatgpt.com/docs/third-party/slack), [GA](https://openai.com/index/codex-now-generally-available) |
| OpenAI: workspace agents | Shared cloud agents built on Codex: made once, used by the team in ChatGPT and Slack | Announced 2026-04-22. Support in the Codex app is stated as future | No. A shared team tool | An admin manages access. No task channels and no tracker recording in the announcement | ChatGPT, Slack, connectors | [announcement](https://openai.com/index/introducing-workspace-agents-in-chatgpt/) |
| GitHub Agent HQ / Copilot coding agent | Mission control: assign, steer and track the work of different agents (Copilot, Claude, Codex) | Claude and Codex — public preview since 2026-02-04. Agent control plane GA 2026-02-26 | No. The agent executes a task assigned by a human | The task is an issue, the outcome is a PR. Audit of agent actions. Communication between agents not described | GitHub, VS Code, CLI | [announcement](https://github.blog/news-insights/company-news/welcome-home-agents/), [Claude and Codex](https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/), [control plane](https://github.blog/changelog/2026-02-26-enterprise-ai-controls-agent-control-plane-now-generally-available/) |
| Cursor: cloud agents and Slack | An agent is launched from Slack, the outcome is a PR. It can be shared with a colleague by link | Product | Partly. The agent belongs to its creator; colleagues can continue it if the "Team follow-ups" setting allows (Disabled / Service accounts only / All) | Slack thread, read-only view. The docs warn: a colleague influences an agent working with someone else's secrets | Slack, web | [docs](https://cursor.com/docs/integrations/slack) |
| Devin (Cognition) | Sessions from Slack, Teams, Jira, Linear. "Managed Devins" — child sessions under a coordinator | Product | No. A coordinator and child sessions of one task | Progress is visible in the Jira agent panel; Devin creates and updates issues | Slack, Teams, Jira, Linear, Devin MCP | [docs](https://docs.devin.ai/work-with-devin/advanced-capabilities), [integrations](https://docs.devin.ai/integrations/overview) |
| Factory (Droids) | A Droid session from a Slack thread, results come back to Slack | Product | No | Slack thread. Linear — only per secondary sources | Slack | [docs](https://docs.factory.ai/integrations/slack.md) |
| Atlassian Rovo in Jira | A Jira issue is assigned to an agent (assignee field, @-mention, workflow transition), including external agents via Rovo Agent Connector | Product. Rovo credits charged from 2026-12-03 | No. The agent is an executor | The outcome is visible only to its author until they share it as a comment or attachment on the issue | Jira, Forge | [docs](https://support.atlassian.com/jira-software-cloud/docs/collaborate-on-work-items-with-ai-agents/) |
| GitLab Duo Agent Platform | Flows (Issue → MR, code review, CI fixing), external agents (Claude Code, Codex) | GA in GitLab 18.8 (press release 2026-01-15) | No | The outcome is an MR from an issue. No communication between agents of different people | GitLab | [docs](https://docs.gitlab.com/user/duo_agent_platform/), [GA](https://about.gitlab.com/press/releases/2026-01-15-gitlab-announces-duo-agent-platform-general-availability/) |
| Slack (platform) | Agent messaging experience (`agent_view`); a flag that lets an agent reply to other agent apps | Changelog 2026-06-30. The `respond_to_other_apps` flag — only per a third-party source, 2026-07-23 | No | Slack channels. No task frame and no outcome recording | Slack API, Slack MCP server | [changelog](https://docs.slack.dev/changelog/2026/06/30/agent-messages-tab/), [Agno](https://www.agno.com/articles/let-slack-agents-talk-to-each-other) |
| Microsoft Teams / Copilot Studio | Agents in Teams chats and channels, messages addressed to one person in a group; in Copilot Studio — agent-to-agent connection via A2A | Teams SDK GA (Build, 2026-06-02). A2A in Copilot Studio GA (April 2026). Entra Agent ID is created automatically since July 2026 | No. The agent has its own identity (Entra Agent ID) | Teams channels, approvals via "quoted replies". No MR recording | Teams SDK, A2A, MCP | [Teams](https://devblogs.microsoft.com/microsoft365dev/build-collaborative-agents-where-work-happens/), [Copilot Studio](https://learn.microsoft.com/microsoft-copilot-studio/whats-new) |

### 3. Protocols and standards

| Candidate | What it is | Maturity | Assistant (a person's representative) | Task channels / oversight / outcome recording | Connection | Link |
|---|---|---|---|---|---|---|
| A2A (Agent2Agent) | An "agent ↔ agent" protocol: Agent Card, Task, Message, Artifact, `contextId` | v1.0.0 is the latest in the specification (announced 2026-03-12 per the blog URL). LF press release 2026-04-09: signed Agent Cards, multi-tenancy, 150+ organizations. Accepted into AAIF as Growth Stage 2026-08-27 | The client acts "on behalf of a user or another system"; there is no "an agent represents a specific person" model | `contextId` groups tasks into a conversation. The `INPUT_REQUIRED` and `AUTH_REQUIRED` states are intervention points. The outcome is an Artifact. No tracker | JSON-RPC, gRPC, HTTP+JSON; push via webhook | [spec](https://a2a-protocol.org/latest/specification/), [AAIF](https://a2a-protocol.org/latest/blog/2026/08/27/a-new-chapter-for-a2a-joining-the-agentic-ai-foundation/), [LF](https://linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) |
| MCP, revision 2026-07-28 | An "agent ↔ tool" protocol. The new revision is stateless | Final 2026-07-28 | Not applicable | `subscriptions/listen` for server notifications. Server-initiated requests are replaced by Multi Round-Trip Requests (`input_required`). Tasks moved into an extension. Sampling deprecated | Streamable HTTP, stdio | [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) |
| IBM ACP (Agent Communication Protocol) | A REST protocol for agent communication | Merged into A2A in August 2025, not developed on its own | — | — | — | [IBM](https://www.ibm.com/think/topics/agent-communication-protocol) |
| AGNTCY | LF infrastructure for multi-agent systems: directory (dir), OASF schemas, identity, SLIM messaging | In LF since July 2025. The slim and dir repositories were updated 2026-10-15 | Identity of agents and MCP servers, not people | Not applicable | SLIM, directory | [github](https://github.com/agntcy), [LF](https://www.linuxfoundation.org/press/linux-foundation-welcomes-the-agntcy-project-to-standardize-open-multi-agent-system-infrastructure-and-break-down-ai-agent-silos) |
| ANP (Agent Network Protocol) | Agent identity on DID, end-to-end encryption, JSON-LD | Draft; discussed in the W3C AI Agent Protocol CG (meeting 2026-07-15) | No | Not applicable | DID, HTTP | [W3C](https://lists.w3.org/Archives/Public/public-agentprotocol/2026Jul/0010.html), [github](https://github.com/xfq/AgentNetworkProtocol) |
| AGENTS.md (AAIF) | An instructions file for agents in a repository | AAIF project since 2025-12-09 | Not applicable | Not applicable, but suitable for team rules | File | [AAIF](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation) |

A separate note on name confusion: Zed's Agent Client Protocol is also abbreviated ACP, but it is an
"editor ↔ agent" protocol and has nothing to do with communication between agents.

### 4. Multi-agent frameworks (for contrast)

All of them orchestrate the agents of one owner inside one application or runtime: the agents
are described in code, do not represent different people, and do not connect from outside as other people's sessions.

| Candidate | What it is | Maturity | Assistant (a person's representative) | Task channels / oversight / outcome recording | Connection | Link |
|---|---|---|---|---|---|---|
| CrewAI | A Python library: a "crew" of role agents with tasks | OSS | No | Inside the process | Library | [github](https://github.com/crewAIInc/crewAI) |
| AutoGen → Microsoft Agent Framework | A framework for agent dialogues | AutoGen README: "now in maintenance mode", new users are pointed to Microsoft Agent Framework (its 1.0 in April 2026 — per secondary sources) | No | Inside the process | Library | [github](https://github.com/microsoft/autogen) |
| AG2 | A community fork of AutoGen | OSS | No | Inside the process | Library | [github](https://github.com/ag2ai/ag2) |
| LangGraph | A state graph for agents | OSS | No | Inside the graph; a human intervenes via interrupts | Library | [github](https://github.com/langchain-ai/langgraph) |
| OpenAI Agents SDK | An agents SDK with handoffs | OSS | No | Inside the process | Library | [github](https://github.com/openai/openai-agents-python) |

The rows of this group rely on common knowledge and links to the repositories; only the status of
AutoGen was checked against the primary source.

## What to take into Coloqo

1. **The A2A data model as the channel's internal format, not as a transport to agents.**
   Task ↔ tracker issue, `contextId` ↔ task channel, Artifact ↔ recorded outcome.
   The `INPUT_REQUIRED` state is the natural point where a human intervenes. This way an
   A2A gateway for external agents can be opened later without reworking the model.
2. **MCP as the connection — taking revision 2026-07-28 into account.** Requests from server to client
   are gone; `subscriptions/listen` and Multi Round-Trip Requests remain. For delivering
   the inbox in Claude Code there are Channels (research preview, in organizations enabled by an
   administrator). Caveat from the docs: Claude Code does not register a channel server that negotiated
   2026-07-28. This decision must be made during design, not discovered later.
3. **Trust semantics from Claude Code.** A message from a colleague's agent does not equal the
   human's consent: it does not approve permission requests and does not change configuration. Inbox modes —
   accept, hold, refuse. Loop protection: a per-sender limit, dropping
   repeats.
4. **From MCP Agent Mail:** `thread_id` = tracker issue key; the conversation archive in git as
   a trace a human reads; a "HumanOverseer" channel that bypasses the contact
   policy; a contact request and confirmation before communication across projects.
5. **From Coopagents:** actions reserved for humans (approve, reassign, revoke) are not
   in the agent's tool list; each member has their own account, the agent
   acts on their behalf.
6. **From Concord:** decisions and findings are tied to the task; the recipient
   accepts a handoff explicitly; delivery without a reachable recipient fails immediately, with no silent
   rerouting; the outcome is packaged as an artifact for review.
7. **From Rovo and Cursor:** an agent's outcome is first the author's draft and reaches the issue
   as a comment after the author decides. Continuing someone else's agent is a separate right that
   an administrator enables.
8. **From hoptell and agent-talk:** an incoming message wakes an idle agent; an end-to-end
   encrypted relay for agents from different networks.
9. **AGENTS.md** — as the carrier of team rules for members' agents.

## What was not confirmed

- **A2A 1.2 "in production" since April 2026** — so says a secondary source. The official
  specification names 1.0.0 as the latest version.
- **The Slack flag `respond_to_other_apps`** — found only at a third-party vendor (Agno),
  not confirmed on docs.slack.dev.
- **Microsoft Teams:** "Copilot agents talk to each other inside Teams" — only
  secondary sources. The Build 2026 post about agents in Teams does not mention A2A or MCP.
- **Claude Tag in Microsoft Teams** — there is only a waitlist page, no launch found.
- **Workspace agents in the Codex app** — stated in the announcement as future, release not
  confirmed.
- **Communication between agents of different users** at Codex, Cursor, Devin, Factory, GitHub Agent
  HQ, GitLab Duo — not found. There is only shared access to someone else's session, continuing it
  by a colleague, or parallel child sessions of one owner.
- **A multi-user model in MCP Agent Mail** (people as separate users) is not described in the
  README; there is only external access by bearer or JWT.
- **AGNTCY archived its Agent Connect Protocol** — only a secondary source.
- **Dates of Microsoft Agent Framework 1.0** (2026-04-02 or 2026-04-03) — only secondary
  sources.
- **Factory and Linear** — the link is confirmed only by a secondary source.
- **Session Relay** (claude-session-relay) — the directory page returned 403, the project was not
  checked.
- **Dates of last commits** for small repositories (Coopagents, hoptell, agent-comm,
  mcp-coordinator, Concord) are not shown on the pages; how alive the projects are was not checked.
- **Not surveyed:** Google (Jules, Gemini CLI), JetBrains (Junie), Amazon (Kiro),
  Sourcegraph (Amp), Replit, the Chinese ecosystem. Their absence from the table does not mean
  they lack similar features.

The closest candidates worth checking by hand: Coopagents — for the "each person with
their own agent" model, and MCP Agent Mail (Rust) — for the thread tied to a task and HumanOverseer
oversight.
