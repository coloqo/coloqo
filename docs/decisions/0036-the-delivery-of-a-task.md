# 0036. The delivery of a task

**Date:** 2026-11-09 · **Question:** a month plan's deliveries had no place in Coloqo, and some of
them are made by several tasks · **Refines:** decision 0031

Decision 0031 left "a task's product delivery as an optional one-line field apart from the
description" for later. On 2026-11-09 the prototype team moved its month plan into the tracker and
found deliveries that several tasks work for; tried as sub-promises, they turned every promise
into a goal. The working file is `docs/tasks/2026-11-09-month-plan-in-the-tracker.md`, question 1.

## Decision

**A delivery is a text field of the task**: the task's meaning in the business's language — what
value the task gives — written by rules and in a style of its own, beside the technical
description. It has no data of its own: no dates, no audience field, no workflow. Its edits are
kept in the task's timeline, as the description's are.

**A task may work for another task's delivery.** A delivery several tasks work for is stated in
one of them, the largest or the central one; another task with no delivery of its own is linked
to it: "works for the delivery of T-12". The rules:

- the link points to a task of the same Team that states a delivery;
- a task that works for another's delivery states none of its own, so links never chain;
- a delivery that tasks work for is not cleared while they do: they are unlinked first;
- a subtask works for its task's delivery by being its subtask; it states none and links to none;
- deliveries and links belong to tasks, not to promises: a promise is product-level already;
- linking is planning: refused without the tracker (decision 0032), as moving a task is (0034).

A task shows its delivery, the delivery it works for, and the tasks that work for its own. The
move of a link is kept in the task's timeline (from → to).

Who may edit them: anyone who may edit the task. An Assistant edits them by `create_task` and
`edit_task`; a human in the web edits the delivery's text on the task's page, and links through an
Assistant for now.

## Why

- A delivery has nothing but its product statement (the author): a type of task or a grouping of
  its own for it would be "too much".
- A link keeps the delivery where it is written and lets a separate story with its own subtasks
  work for it, which a subtask could not: a task with subtasks does not become a subtask.
- No chains and no orphaned links keep "the tasks of a delivery" one query away.

## Not decided here

- The rules and the style of a delivery's text: the Team's rules, when they exist.
- Linking in the web.
