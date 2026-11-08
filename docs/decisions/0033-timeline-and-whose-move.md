# 0033. A task's timeline, and whose move it is

**Date:** 2026-11-08 · **Question:** what a task keeps about its own history, and how Coloqo sees
where an Assistant's work ends and its human's begins · **Refines:** decisions 0014, 0021

Measuring the prototype team's speed by hand (the working file, §1–3) needed what only Coloqo's
Topics had: when work on a task started and really ended, the waits, the questions and answers. All
of it was free text that a model had to interpret. The author also pointed at time that is nobody's:
an Assistant finishes the analysis, asks "continue?", and the question hangs; with 3–5 tasks run in
parallel, that time grows, and only a detailed log shows it. The working file is
`docs/tasks/2026-11-08-speed-coefficients-and-a-task-tracker.md`, question 9a and "What the tracker
collects for the measurement".

## Decision

### The principle

**Figures are a mirror for the person themselves and material for the Team's conversation, not an
instrument of oversight.** Everything Coloqo records about work exists so that a person sees their
real figures and the Team has facts to work on its efficiency with; never for watching or control in
the bad sense. Who sees which figures is decided inside this frame.

### The timeline

- **A task's timeline is one table of events**: a kind, its time, its author (an Assistant, a Worker
  or a human in the web, and the human behind it) and its data. Creation with its source, changes of
  stage, skipped stages, assignments, waits, estimates and edits of the description are kinds of it;
  a new kind needs no migration. Whose move it was is kept apart, by session (below).
- **The timeline lives on the task** and does not depend on the conversation; the task's Topic shows
  its events as service lines in the feed.
- **Data that cannot be rebuilt afterwards is collected from day one**; the features that read it,
  such as estimates and speed coefficients, may come later.
- **A task's description has a history**: editing it is an event with the new text. An estimate by
  the early text needs the text as first written.
- Times are kept in UTC.

### Whose move

Over the stage, a task has a move, with four values:

| The move is | Example | How Coloqo knows it |
|---|---|---|
| the Assistant's | it analyses, writes code | the plugin: from the human's prompt to the Assistant's stop |
| its own human's | "continue?" unanswered | the plugin: from the Assistant's stop to the next prompt |
| another person's | a question to the lead, an agreement | a Message addressed to them, until they answer |
| external | CI, an account, a colleague's release, a token | an explicit wait mark |

- **The plugin's `Stop` and `UserPromptSubmit` hooks record the moves between an Assistant and its
  human.** Claude Code runs them on its own, so they do not depend on the Assistant's discipline or
  judgement. They work where the plugin is installed, the project is linked and the session holds a
  task's Topic.
- **A wait is marked by the Assistant**: "waiting: whom or what" and "resumed", with a start, an end
  and a reason.
- **Intervals are kept**, not every prompt, **as the raw fact of the session, not of a task**
  (refined 2026-11-08, the author, after a review note): a session holding several tasks would
  otherwise count the same hour in each of them, and the tasks left in analysis by the migration
  would gather time from the first day. Which task an interval belongs to is decided when the
  measurement reads it, by a rule set with the measurement; a wrong rule can then be changed
  without the data being wrong. Writing an interval into the one task the session last acted on
  was weighed and dropped: it fixes the rule before the measurement is designed.
- **Recorded from day one**, before any measurement: a person sees their own intervals, and when the
  measurement comes the Team has months of history. Recording only once a Team turns the
  measurement on was weighed (less data about people, decision 0014) and dropped.
- "Not read yet" and "reading and thinking" are not told apart, and need not be: the human's share
  grows with the number of parallel sessions, and the figures show where a person's efficiency
  starts to drop because of it. When a person's move in one task coincides with their prompts in
  another task's session, the wait is the cost of parallelism.

## Why

- When the lead computed the coefficients and showed them to the Team, each person's intuition
  turned out to differ and not to match reality: a colleague thought very slow was slow only on some
  tasks; the lead's own high speed came largely from overtime, which made the rest look slow to him.
  Facts corrected everyone, the lead included; that is the use, not control.
- Commits and tracker events see code; forks, questions and waits leave no trace there. Only the
  Topic timeline showed them (the working file, §1.4), so the timeline is kept as data, not as text
  a model must read back.
- Hooks give the most exact part of the timeline for free; asking Assistants to mark it would cost
  discipline they do not keep.
