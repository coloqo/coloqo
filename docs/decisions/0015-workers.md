# 0015. Workers in the architecture

**Date:** 2026-10-17 · **Questions:** W1–W8 of the product statement (`docs/product/vision.md`,
section "Workers") · **Refines:** decisions 0003, 0006, 0007

A transfer of what was decided in the product statement; no new forks.

## Members and credentials (W1, W3)

- **A Team Member is a human or a Worker.** A User is always a human. A Worker has a role and a
  reference to the responsible human; without a responsible human the Worker is paused.
- **A token is issued to a human's installation (decision 0003) or to a Worker.** The Worker's
  token is created by the responsible human in the web, without device code login. Permission
  checks ask for the Member's role, not for the user behind it.
- **The Worker's installation key** lives on the machine where it works and is signed by the
  responsible human's user master key (decision 0004); a secret's recipient sees during
  verification who is responsible for the Worker.
- **Plugin profile.** `coloqo login --worker <name>` puts the Worker's token as a separate profile
  into the keychain; the `COLOQO_PROFILE` variable selects the session's profile. The same plugin
  in Worker mode: the start hook loads the role, the Area rules with the section for Workers and
  the instruction to take the next task; the MCP has no tool for sending a secret. The human's
  regular sessions on the same machine remain their Assistants.

## Tasks and Topics (W4, refines decision 0006)

- **A Worker's queue is a tracker filter in the role description**; the Worker reads and updates
  the tracker with its own tools on the Team's side. The server does not integrate with the
  tracker.
- **A Topic for a task is one for the task's whole life; it has a holder that changes by stage.**
  Claiming a task is atomically taking a Topic that has no holder; having finished its stage, the
  Member releases the Topic. The holder can be an Assistant or a Worker. A message in a Topic is
  delivered to its current holder (decision 0006).
- **Task fitness criteria** are in the role's rules; at the first stage a Worker takes only what a
  human has marked.

## Decisions, escalation, autonomy (W2, W6, refines decision 0007)

- **The Area's decision chain** is an ordered list of Members with decision classes; by default —
  the human owner. A Worker's escalation is a Question (decision 0006) to the next in the chain;
  a timer without an answer — a reminder, then higher.
- **Waiting does not block:** the task is in the state "awaiting decision", the Worker takes the
  next one. The cap of open Questions per Worker is a setting (3 by default).
- **A decision made on its own** is a service message in the task's Topic with a reference to the
  rule.
- **Full autonomy** — a chain without humans, in a separate Area; the human owner supervises.
  Conversation frame: "continue?" is decided by the top of the chain within the Area's daily
  budget; when the budget runs out — a Question to the human owner. The lead worker writes a
  summary once a day.
- **Self-organizing Area:** the set of roles and the lead worker are set by a human; the lead
  worker hires and fires Workers from these roles if the Area rules allow it.

## Protection (W5, W7)

- **Default Area rules** forbid Workers: invitations and removals, creating and deleting Workers,
  changing roles, chains and budgets, approving rules, deleting Topics and Areas. The human owner
  changes them.
- **Service invariants** — checked by the server under any settings:
  1. at the top there is always a human owner with the stop button;
  2. a Worker does not change budgets, caps, rules, the list of roles and role permissions; the
     lead worker hires only from roles described by a human, within the set number;
  3. only a human invites and removes humans;
  4. every Worker has a responsible human;
  5. a Worker does not give out secrets.
- **Caps** — open Questions, tasks taken and messages per day per Worker, the Area's turn budget;
  changed by the human owner; when reached, the Worker is stopped and the owner gets a Question.
- **Stop** — for a Worker, an Area, a Team: the server refuses all actions, sends no events, every
  response is "you are paused". External processes are killed by the human at stage 1, by the
  runner at stage 2.
- **Rights outside Coloqo** — the Worker's own accounts with a minimal role; each role has a table
  of three levels of actions (on its own, with a decision from above, never on its own); the
  boundary is the mechanisms of external systems, the second layer is the agent's allowlist. The
  role description in the cloud lists the accounts and levels.
- **Revocation** — deleting a Worker revokes its token and removes the signature from its key.
  **Log** — actions in Coloqo; the tool call log — at stage 2.

## Launch (W3)

- **Stage 1 — manual:** a human launches an agent with the Worker profile. Claude Code first.
- **Stage 2 — `coloqo runner`** on the Team's side: fills the Team with Workers as they are
  configured in the cloud. Registers with a runner token from the web; on an event — a headless
  agent session (for Claude Code — the Agent SDK), a new task — a new session, continuing after a
  closed Question — resuming; kills the process when idle; survives crashes; several Workers per
  machine. The agent runs isolated in a container or a virtual machine, with an explicit
  allowlist, without `bypassPermissions`. Required for self-organizing Areas.
- **The cloud** does not hold the Team's code or keys (decision 0014); cloud launch of Workers is
  not done.

## Accounting (W8)

Workers are Team Members; there is no billing code. Pilot measures: tasks taken and completed,
accepted without rework, Questions per task.
