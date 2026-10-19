# 0022. What reaches a session: its focus

**Date:** 2026-10-19 · **Question:** a team lead with several sessions open got every Message of
the Team in each of them · **Refines:** decisions 0006, 0020

The watch prints a line for every relevant event, the prompt reminder lists Topics addressed to
the person, and the session start shows the Inbox — in every session alike. A developer barely
notices; a team lead with three to five sessions open gets each Message of each developer five
times. The author asked to choose per session what it hears, for instance one session per
developer, so that switching terminals is switching between people.

## Decision

Every session has a **focus**: what is brought into it unasked. Reading on request does not
depend on it: the Inbox, `read_topic` and the web see everything as before (decision 0020).

| Focus | What reaches the session |
|---|---|
| `all` | everything of the project's Team, as before |
| `mine` | only Topics this project's Assistant holds or writes in (sessions in one folder share it) |
| `people: bob, carol` | Messages of these people and their Assistants in any Topic, and their new Topics |
| `quiet` | nothing; the Inbox only on request and at session start |

- **Switching.** `/coloqo:focus mine`, `/coloqo:focus bob`, `/coloqo:focus all`, or in words
  ("listen only to bob here"), which the model turns into the plugin's `set_focus`.
- **Where it lives.** In the plugin on the person's computer, per session; the server does not
  keep it. Several sessions in one project can follow different people: Claude Code tells the
  watch, the tools and the hooks which session they serve (`CLAUDE_CODE_SESSION_ID`).
- **Default.** New sessions start with `all`; the plugin's settings on the computer change the
  default, e.g. a team lead sets `mine`.
- **Nothing addressed to the person is lost.** A Message to them that no session's focus lets
  through waits in the Inbox, in the web with the bell, and in the summary at the next session
  start. Sessions do not know of each other, so none of them is guaranteed to show it unasked.

## Why

- What a session hears should follow what it works on; the same stream in every terminal is
  noise, and noise teaches people to ignore Coloqo.
- People work differently: a developer wants the Team, a lead wants a session per developer or
  only their own Topics. A setting per session serves both without a rule for everyone.
- The focus decides delivery only, on the person's computer, so it needs no server change and
  hides nothing: everything is still there on request.
