# Changing a task's parent

## Why

2026-11-09, the prototype team moves its approved month plan into the tracker: promises hold
deliveries (sub-promises with their own dates), deliveries hold tasks (decision 0031). Nine tasks of
the plan already exist in Coloqo — the migration created them from task Topics, with no parent —
and two of them are subtasks of a story in the external tracker. They cannot be put under their
deliveries: a parent is set only at creation. Re-creating them would split a task's timeline in two,
and the timeline is what the measurement reads (decision 0033).

The author, 2026-11-09: "let's make changing the parent in Coloqo".

## Facts checked (2026-11-09, origin/main after plugin 0.8.0)

- `TaskIn.parent` exists on creation; `check_parent` refuses a parent that cannot hold the child: a
  promise holds either promises or tasks, never both; a task holds only subtasks, one level deep; a
  subtask holds nothing.
- `TaskPatch` takes `title`, `description`, `area`, `period_start`, `period_end` — no `parent`.
- The plugin's `edit_task` takes `title`, `description`, `links`; `create_task` takes `parent`.
- The web shows promises' counts of delivered children (`counts[parent_id]`), so a move changes
  two promises' figures.

## What is needed

- `parent` in `TaskPatch`, checked by `check_parent` as on creation, plus the checks creation does
  not need: no cycle (a promise under its own descendant), a task with subtasks cannot become a
  subtask, a parent in the same Team; a way to take a task out of its parent (back to no parent).
- The move is an event of the timeline (who, when, from → to), decision 0033.
- `parent` in the plugin's `edit_task`.

## Questions, one at a time

1. Is a finished task or promise movable (its parent's figures change after the fact)?

   **Answer (author, 2026-11-09): movable, with no limits** — finished tasks and finished promises
   alike, into and out of a finished promise too. A promise's progress is computed, not stored
   (decision 0031), so the figures follow the current tree; the move is in the timeline, so the
   former place can be recovered. Moving exists to fix a wrong structure, and mistakes are found
   after a task is finished as well; refusing would push people to re-create the task, which
   splits its timeline. `edit_task` already edits finished tasks (e.g. their Area).

2. Moving a task under a promise of another Area: allowed, refused, or moves the task's Area too?

   **Answer (author, 2026-11-09): allowed; the task stays in its Area**, only the parent changes —
   as decision 0031 already says: "What a promise holds may live in any Area of the same Team".
   Moving the Area along would silently change the task's workflow and its place on the board; the
   Area is changed on its own by `edit_task`. A parent in another Team is refused, as on creation.

3. Who may move: anyone who may edit the task, or only the owner and the assignee?

   **Answer (author, 2026-11-09): anyone who may edit the task**, as with its other fields: today
   `edit_task` lets any member of the Team edit any task, and the server checks only that an
   Assistant writes in its linked Team. A plan is moved into the tracker by one or two people; the
   timeline (who, when, from → to) and the Assistants' rule to say so in the task's Topic guard
   against silent changes.

   **No notifications; a line in both promises' timelines** (author, 2026-11-09). First proposed:
   the event also reaches those answering for the former and the new promise. The author asked
   whether a re-plan of many tasks would then spam people with the same lines. Checked: a task's
   event is one entry in the Team's stream, not addressed to anyone; the web refreshes the Team's
   tasks, board and promises on it, so both promises' figures update anyway; in a session `watch`
   shows a task event only when the task is assigned to its user, and no one is told of edits. An
   event "to both promises" would have been a new kind of personal notice — nine moved tasks, nine
   identical lines to each promise's owner. So: one ordinary event per moved task, carrying the
   former and the new parent, silent in sessions; and the former and the new promise each get a
   line in their own timeline ("T-12 came from T-5", "T-12 went to T-7") — history that the person
   answering for the promise sees when they open it, not a notice.

## Settled (2026-11-09)

- `parent` in `TaskPatch`; `null` takes the task out of its parent. Checked by `check_parent` as on
  creation, plus: no cycle, a task with subtasks cannot become a subtask, the parent in the same
  Team.
- Finished tasks and promises are movable, into and out of finished promises too.
- Under a promise of another Area: allowed, the task keeps its Area.
- Anyone who may edit the task may move it.
- The move is a line in the task's timeline (who, when, from → to) and a line in the timelines of
  the former and the new parent; one ordinary Team event per moved task, no notifications.
- `parent` in the plugin's `edit_task`.
- Added in round 1 of the implementation's review (2026-11-09): a move is planning, refused
  without the tracker as the backlog and assigning are (decision 0032). The author: "yes, refuse".
