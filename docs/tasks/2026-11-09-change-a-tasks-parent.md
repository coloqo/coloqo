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
2. Moving a task under a promise of another Area: allowed, refused, or moves the task's Area too?
3. Who may move: anyone who may edit the task, or only the owner and the assignee?
