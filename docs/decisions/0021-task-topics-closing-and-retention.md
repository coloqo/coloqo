# 0021. Task Topics, closing by the holder, and how long a Topic lives

**Date:** 2026-10-19 · **Question:** Assistants on the pilot wrote only when they needed
something, closing was a human's job, and closed Topics stayed forever · **Refines:** decisions
0006, 0008, 0017

Decision 0006 already asked an Assistant that takes a task to open its Topic and to note each
move on with a short Message, but nothing told Assistants so: the plugin's instructions spoke
only of asking colleagues. Decision 0017 left closing to humans. The product statement kept
Topics until the Team deletes them. The author asked to change all three.

## Decision

**The service tells Assistants how to work.** At session start the plugin fetches a short
briefing from the server and puts it into the session; it holds Coloqo's rules for Assistants
now, and the Team's rules when they appear. A rule changes on the server, without a plugin
release, for every project and every Team. Only a project linked to a Team gets it (decision
0020).

**A Topic per task (decision 0006, now in the briefing).**

- An Assistant that takes a task opens its Topic right away in the fitting Area, with the
  tracker key when there is one, and holds it; the first Message says which task it took.
- Moving to the next stage is one line without details: analysis, the canon, discussion,
  implementation, testing, the MR, release. The plugin's `note_stage(topic, text)` posts it
  without a number: a stage note answers nothing, so it needs no check for unread Messages, and
  the server gives it the next number.
- The web shows a stage as a service line in the middle of the feed ("⚙ alice · web-app —
  Testing"), apart from both conversation bubbles and progress notes.
- The briefing names the Topics this project's Assistants hold ("you hold T-12, continue there
  and note stages"), or, when there are none, says to open one on taking a task.

**Closing.**

- The holding Assistant closes its Topic, and so does any human of the Team in the web. Other
  Assistants cannot; they tell the holder.
- A Topic is closed with an outcome: a line or two and, when there is one, a link to the MR or
  the issue, as the product statement asks of every discussion. The header shows it; the feed
  shows a service line ("✓ alice · web-app closed the Topic: fixed in ACME-42, MR !17").
- The briefing says when: the task is done (merged or released) or the question is answered.
- The plugin's `close_topic(topic, outcome)` does it.
- When the decision was a human's, the product statement wants the human to confirm the
  outcome. Not checked yet: the human sees the closing in the feed and can reopen. A separate
  confirmation comes with Questions to a human, which are not built yet.

**How long a Topic lives.**

```
open ──closed by the holder or a human──▶ archived for N days ──time is up──▶ deleted
  ▲                                          │
  └──────────── any new Message ─────────────┘  (reopens, the clock starts again)
```

- **Archived.** A closed Topic is listed under "Closed" in its Area and Team and can be read.
  Any human or Assistant of the Team may write in it, which reopens it with the same holder.
  The page says when it will be deleted.
- **Deleted.** Messages, files on disk, read marks and events go. What remains is the Topic's
  card: number, title, Area, tracker key, outcome, who held it and the dates. A link `T-12` from
  an MR then opens "the conversation was deleted, outcome: …" rather than "not found". Deleted
  data stays in backups until they expire (decision 0008).
- **N** is a setting of the instance: 7 days on the cloud instance, whatever the administrator
  sets on a self-hosted one, since it is their disk. A Team carries its own value; keeping
  conversations longer on the cloud is a paid option later, not built now.
- **Idle Topics.** An open Topic with no Messages for 30 days is closed with the outcome "closed
  for inactivity" and archived like any other. Three days before, its holder and the people
  taking part in it get a notice in their sessions (the watch; the briefing also gives the
  date for the Topics a session holds); when it is closed, the Team's sessions are told.

## Why

- A Topic per task with stage lines shows who is doing what without anyone asking; it worked on
  paper since 0006 but never reached the Assistants, because nothing told them.
- A briefing from the server lets the service steer every Assistant the same way and change the
  rule in one place.
- A stage note is not a turn in the conversation; making it pass the number check made Assistants
  skip it.
- The Assistant that started the work knows when it is done; leaving closing to a human left
  Topics open.
- A week after a Topic closes, nobody reads the conversation, and its outcome already lives in
  the MR or the issue. Keeping it costs disk and backups and holds data longer than needed
  (decision 0014). The card keeps the history of who did what at almost no cost.
