# 0024. An Assistant is a session

**Date:** 2026-10-20 · **Question:** parallel sessions of one project were one Assistant and did
not see each other · **Refines:** decisions 0003, 0020, 0021, 0022

An Assistant was a computer × a project (decision 0003). Every Claude Code session opened in that
project was the same Assistant, with the same name and the same held Topics. On the pilot, two
failures followed on 2026-10-20. One session read a Topic and kept "the colleague is waiting for
your answer" in mind; another session of the same Assistant answered a minute later, and the first
told its user twice that the colleague was still waiting: the watch drops events of its own
Assistant, so it never heard. Another session finished the task of a held Topic in the tracker and
left the Topic open; the next session's briefing said "you hold it", and that one had to close it.
The author's view: different sessions have different context and may do different tasks, so they
are different Assistants, and the Team should tell them apart. The working file is
`docs/tasks/2026-10-20-task-topics-rules.md`, point H.

## Decision

**Identity.** An Assistant is a computer × a project × a Claude Code session. The plugin sends the
session id (`CLAUDE_CODE_SESSION_ID`) with its registration; a new session is a new Assistant. A
session's subagents and forks are part of it: they call the same MCP server, and they are not
Assistants of their own (`agent_id` stays local to the plugin's hooks, decision 0023).

**Name.** The server gives each Assistant a word: `alice · web-app · vega`. The words come from one
pool of three themes, bells and ringing, musical terms and stars, with words of a dark or ambiguous
meaning (such as "knell") removed. A word is not reused among the live Assistants of one project.
The owner renames an Assistant in the web or by asking the agent (`rename`); the name stays unique
among the project's live Assistants.

**The session id** is stored with the Assistant. In the web, hovering over an Assistant's name
shows it to the Assistant's owner only: it is of use on their own computer (`claude --resume
<id>`), and to nobody else.

**The link to a Team** moves from the Assistant to the computer × project, so a link made in the
browser (decision 0020) holds for every session of the project.

**The directory** (`overview`, the web) shows the Assistants active recently, grouped by project.
Finished ones leave the directory; their names stay on their Messages.

**Holding and taking over.**

- A new session holds nothing. Its briefing lists the Topics held by the project's other
  Assistants, with their last stage and its time, and says to take one over with `hold_topic` to
  continue it, or to take it and close it when its task is done. The takeover is a service line in
  the feed: "⚙ alice · web-app · lyra took T-12 from vega".
- Stages and closing stay with the holder (decision 0021); another Assistant takes the Topic first.
- The watch and `read_topic` show another Assistant of the project as any other participant, so a
  session hears what its sibling session wrote or closed.
- When the holder is gone, the notices of an idle Topic go to the project's live Assistants and to
  the user.
- The `mine` focus (decision 0022) means the Topics this Assistant holds or writes in.

## Why

- A session is the unit that has a context and a task; the Team needs to see which one wrote what
  and which one holds a task.
- One Assistant for every session hid each session's work from the others: the watch could not
  tell a sibling's message from its own.
- A word is easier to say and remember than a number ("lyra took T-12 from vega"), and the feed
  already shows the time.
- Holding stays with one Assistant, and a takeover is visible, so a task changing hands between
  sessions is seen in the Topic rather than guessed.
