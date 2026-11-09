# 0037. The plan

**Date:** 2026-11-10 · **Question:** a Team's approved month plan — its promises, its work outside
promises, its off-plan work and what that work drops — had no place in Coloqo · **Refines:**
decisions 0031, 0032

On 2026-11-09 the prototype team tried to move its approved month plan into the tracker and stopped:
Coloqo lacked what the plan needs. The discussion is in
`docs/tasks/2026-11-09-month-plan-in-the-tracker.md`, questions 2–6 and the points settled on
2026-11-10; the delivery (question 1) is decision 0036.

## Decision

**A plan is a light entity of the Team**: a name, a period (a first and a last day, usually a
month), a number of its own in the Team, and three states read from two moments — a draft until a
human approves it, approved, and closed when a human closes it after its period. Who approved and
who closed, and when, is kept. It has no workflow, Topic or discussion of its own. **A Team's plans
do not overlap in time**: the server refuses an overlap. A task is in several plans one after
another, never in two at once; a plan of a larger period around monthly ones would hold plans or
promises, not tasks, and is a decision of its own.

**A plan holds promises and tasks**, by membership, not hierarchy: a task has one parent and may be
in several plans. Adding a promise brings the unfinished tasks under it, at any depth; a task later
created under, or moved under, a member of a plan that is not closed joins that plan by itself; a
task with no promise joins on its own — the Team's work outside promises. **A task leaves a plan
only while it is a draft**: one not started, always; a started one, only before the period
begins; a finished one, never. Once a plan is approved its rows stay, as its history.

**Every row has a mark, set by itself:**

- **planned** — it joined before the plan was approved;
- **found** — it joined after approval and its `source` (the task it was found within) is in the
  plan and was given explicitly by its creator; a `source` the server filled in from the held Topic
  tells where the task came from but does not make it found;
- **off-plan** — it joined after approval otherwise.

A human corrects found ↔ off-plan. Off-plan work names **what is dropped** from the plan; until it
does, the plan shows the row as unfinished ("what is dropped: not named"). **Only a human writes
it**: it is a conscious choice, and an Assistant must not silence the signal with something
plausible. A task that joins is not refused for lacking it: tasks join by themselves when an
Assistant creates them under a planned promise.

**A row may be postponed**: the Team decides not to finish a planned task in this period — in
favour of off-plan work, or because its time was misjudged. The task stays in the plan; postponing
is a state of the row with a required reason, set and undone by a human, kept in the task's
timeline. In a draft whose period has begun, a started task cannot be removed but can be postponed.
The off-plan task's "what is dropped" and the postponed task's reason name each other as text;
neither is derived from the other. Lowering a task's priority stays the board's order.

**Carried** work is read, not marked: a row shows "from <plan>" when the task was in an earlier
closed plan and not done there. A new draft offers the previous plan's unfinished work.

**Closing** fixes each row's result: done (Done, or a promise Delivered, by the period's last day),
cancelled (Cancelled or Withdrawn), or not done; work finished later does not rewrite the month.
The plan then shows planned done and not done, postponed apart, found and off-plan counts, what
off-plan work dropped, and its promises' outcomes.

**No dates on tasks**: decision 0031 stands; a forecast from each member's speed comes with the
estimates. Newcomers' tasks wait unassigned until they log in.

Every join, mark and "what is dropped" goes to the task's timeline (decision 0033). Plans are
planning: with the tracker off they are not created or changed (decision 0032). **An Assistant
creates a plan and fills its draft** (the month plan was first moved by the lead's Assistant).
Approving, closing, adding work after approval, correcting a mark, writing what is dropped and
postponing are a human's, in the web.

## Why

- The month plan is an object of the Team's work: approved, worked by, reviewed at the month's end,
  and off-plan work must name what it drops. Marks relative to a plan keep a task's life across
  months readable.
- Marks set by the moment of approval need no hand work; the unfinished "what is dropped" keeps the
  Team's rule visible without blocking the tasks Assistants create.
- An explicit `source` only: a task the server ties to the held Topic by default may be unrelated
  urgent work, exactly what the rule is there to catch.
- Results fixed at closing keep the month as it was.

## Not decided here

- A plan of a larger period around the monthly ones.
- Moving a plan's draft wholesale into the next period.
