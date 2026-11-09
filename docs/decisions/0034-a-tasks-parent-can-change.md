# 0034. A task's parent can change

**Date:** 2026-11-09 · **Question:** a parent is set only when a task is created, so tasks that
already exist cannot be put under the promises they work for · **Refines:** decisions 0031, 0033

On 2026-11-09 the prototype team moved its approved month plan into the tracker: promises hold
deliveries (sub-promises with their own dates), deliveries hold tasks. Nine tasks of the plan
already existed in Coloqo, created by the migration from task Topics with no parent, and could not
be put under their deliveries. Re-creating them would split each task's timeline in two, and the
timeline is what the measurement reads (decision 0033). The working file is
`docs/tasks/2026-11-09-change-a-tasks-parent.md`.

## Decision

**Editing a task changes its parent too.** A task, a subtask or a promise is moved under another
task or promise of the same Team, or taken out of its parent. The checks of creation apply
(decision 0031: a promise holds either promises or tasks, never both; a task holds only subtasks,
one level deep; a subtask holds nothing), and the ones only a move needs:

- no cycle: a task is not put under itself or under its own descendant;
- a task that has subtasks does not become a subtask;
- the parent is in the same Team.

**Finished tasks and promises move with no limits**, into and out of a finished promise too. A
promise's progress is computed, not stored (decision 0031), so its figures follow the current tree.

**Under a promise of another Area the task keeps its Area**: only the parent changes, as decision
0031 already lets a promise hold tasks of any Area of the Team. The Area is changed on its own.

**Anyone who may edit the task may move it**, as with its other fields.

**The move is kept in three timelines, with no notifications** (decision 0033): the task gets a
line from → to, the former parent a line that the task left it, the new parent a line that the
task came. The Team's stream gets the one ordinary event of an edited task, carrying the former and
the new parent; Assistants' sessions show nothing of it, the web refreshes both promises.

The plugin's `edit_task` takes the parent.

## Why

- Moving exists to fix a wrong structure: tasks made before the plan, a plan reshaped, a task put
  under the wrong delivery. Mistakes are found after a task is finished as well; a refusal would
  push people to re-create the task, which splits the timeline.
- Keeping the Area keeps the task's workflow and its place on the board: moving it in the plan does
  not silently change how it is worked.
- A plan is moved into the tracker by one or two people, a lead or the plan's author; asking every
  assignee to move their own tasks would stall it. The timeline shows who moved what.
- No notifications: a re-plan moves many tasks at once, and a notice per move to those answering
  for the promises would repeat the same line nine times. The promise's own timeline shows the
  history to whoever opens it.

## Not decided here

- Moving a task in the web: the web shows the parent; the move is made by an Assistant or through
  the API for now.
