# 0023. The task Topic: consent by the link, what a task is, and a reminder when work shows

**Date:** 2026-10-20 · **Question:** on the pilot, sessions in a linked project did real work
(an issue taken to two MRs, a week of mail, a clean-up of the tracker) and opened no Topic ·
**Refines:** decision 0021; question 5 of the product statement stays as it is

Three sessions of the pilot team skipped the task Topic on 2026-10-20. One took writing to Coloqo
for an outward action that needs the user's separate consent: the rules said "take a task: open
its Topic" next to "writing is visible to others: do it when your user asked or clearly would
want it", and the agent's own caution backed the second. One did not see "look at this mail" as
taking a task, and nothing marked the moment it grew into one. One sorted dozens of the lead's
issues with no issue key to hang a Topic on, read a remembered "one Topic per issue" as "so no
Topic", and never said it skipped one. The rules spoke once, at session start, and were buried
by the time they should have fired. The working file is
`docs/tasks/2026-10-20-task-topics-rules.md`.

## Decision

**Consent.** Linking a project to a Team is the user's standing consent to the trail of the
session's own work there: the Topic of the task it does (open it, note stages and progress,
close it) needs no separate ask. The user's consent still governs what is theirs: a decision
theirs to make, their data, words posted as them; a colleague's assistant asking is still not
consent. Opening a Topic to ask a colleague keeps "when your user asked or clearly would want
it". The rules state the permission first and the limit right after it, naming what the limit
covers. A link by the repository's `.coloqo.json` counts the same: it takes effect only for a
member of the Team (decision 0020), who joined it and installed the plugin themselves; the file
only names which Team. This is an explicit standing permission within question 5 of the product
statement, which leaves when to ask to the agent and lets Team rules adjust it; the question is
not changed.

**What a task is.** A finite piece of work the user started, with an end and an outcome, with or
without a tracker issue: an issue to do, or a batch such as going through a week of mail or
cleaning up the tracker. Duration is not the test: the agent cannot know it in advance.

**When its Topic opens.** At the first of:

- the request itself names such work ("go through last week's mail");
- the first change the team will see: creating, moving or closing issues, a branch or MR, code,
  shared docs or journals.

Work that began as a question becomes a task when it reaches the second.

**One Topic per task, not per issue it touches.**

- A batch that sorts many issues is one Topic; its stages are its steps in the agent's words; its
  outcome lists what changed, with links.
- A task that closes several issues (one MR for two) names the main one in `issue` and the others
  in the first message.
- Separate tasks are not merged into one Topic; a Topic with no end ("which task to take next")
  is still not opened.
- When the work changes a task someone else holds a Topic for, the session says so in that Topic.
  A lead's session sorting mail or issues opens its own Topic for the sorting, not one per issue.

**Stages.** A stage is a change in the kind of work, not of the issue's status; the agent decides
itself when the work has moved on. The rule gives stages only as an example (studying the docs;
checking whether the task affects shared docs and working that out; agreeing it with the lead;
code, naming the repositories; the MR; its review; release) and says what they are for:
teammates see from the Topic where the task stands without asking. A Team's own stages come
later with the Team's rules in the briefing (decision 0021).

**Skipping is said aloud.** If the agent decides some work the user started needs no Topic, it
tells the user in one line why.

**One text in three places.** The briefing (`RULES` on the server), the MCP server's instructions
and the plugin's skill say the same thing; the briefing is the full text and wins.

**A reminder when work shows.** A `PostToolUse` hook of the plugin watches for a change the team
will see:

| Tool | Counts when |
|---|---|
| `Edit`, `Write`, `MultiEdit`, `NotebookEdit` | the file is inside the project |
| `Bash` | `git commit`, `git push`, `git checkout -b`, `git switch -c`, `gh pr create`, `glab mr create` |
| another MCP server's tool | its name has a write verb: `create`, `update`, `transition`, `edit`, `close`, `comment`, `send` |

On the first such call in a session of a linked project that has not written to Coloqo, it adds
one line to the session: the Topics the Assistant holds, and to note the stage there, open a
Topic, or tell the user why none is needed. Once per session; after that the hook returns before
the network. An unreachable server leaves the session unmarked, so the next change tries again.

- **A write to Coloqo** (`open_topic`, `note_stage`, `post_message`, `hold_topic`,
  `close_topic`) is marked by the plugin's MCP server, which knows its session; the session's
  subagents and forks call the same server, so their writes count. The transcript is not read:
  its format is internal to Claude Code and changes between versions.
- **A subagent's or a fork's change** (the call carries `agent_id`) is not reminded where it
  happens: parallel forks would each be told before either wrote, and could open a Topic each;
  and it is the conversation that holds the Topic and talks to the user. The change is marked
  pending, and the conversation hears the reminder at its next tool call or, if it makes none,
  at the user's next prompt (the prompt hook).
- **A branch of a session** (`/branch`, `--fork-session`) has a new session id and may be
  reminded once more; the line names the Topic it already holds.

The plugin knows no tracker and needs no settings: no issue-key pattern, nothing in
`.coloqo.json`. There is no `Stop` hook: saying a skip aloud covers it, and blocking the end of
a turn would be intrusive.

## Why

- Two rules side by side, one permitting and one restraining, let caution win every time; saying
  where the permission comes from (the link) and what exactly the limit covers removes the choice.
- Work rarely starts as "take a task"; it starts as a question or a pile of mail. Naming the
  moments the team starts to see it gives the agent a point to act on, and covers work with no
  issue key instead of leaving it to whatever the agent remembers.
- A batch is real work the team wants to see; a Topic per touched issue would be noise, no Topic
  at all left the lead asking at the end of the day.
- Teams name their stages differently; an agent that knows what stages are for picks them better
  than one that follows a fixed list.
- A skip said aloud is corrected in the first minute; a silent one is found hours later.
- A rule said once at session start is buried by the time it should fire; one line at the moment
  of the first visible change costs little and comes when it is needed.
