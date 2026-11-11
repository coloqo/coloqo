# Assigning a task from the plugin

## What happened

2026-11-11, the prototype team. The month plan was moved into the tracker with a new member's tasks
left unassigned until they log in (decision 0037). The member has logged in; the lead asked their
Assistant to assign the tasks to them. The Assistant could not: the plugin has no tool for it.
`take_task` assigns only to the Assistant's own user, `create_task` sets an assignee only on a new
task, and `edit_task` does not touch the assignee.

The author, 2026-11-11: "Coloqo is made to work through assistants, not by hand."

The same day the lead set the assignee of one task in the web, and it landed: the task's timeline
shows the `assigned` event, and the member's Assistant moved the task ten minutes later. The web is
not the problem; the rest of the member's tasks wait because an Assistant cannot assign them.

## Facts checked (2026-11-11, plugin 0.12.1)

- **The server already allows it.** `POST /api/team/{team}/task/{number}/assign` with
  `{"assignee": "<pseudonym>" | null}` (`AssignIn`, `assign_task` in `api/tasks.py`). It checks only
  `task_for(..., write=True)`, the tracker (`need_tracker`) and that the task is not finished; there
  is no `actor.is_human` check, unlike `order_task` ("Ordering tasks is done in the web", 403 for a
  plugin). The pseudonym is matched in any case, a leading `@` dropped (`assignee_by_name`); an
  unknown one is 422 with the list of Members.
- **The event:** `assigned` in the task's timeline (from → to) and a Team event `task` that wakes
  every Member's streams (`task_event`, `add_event`). The plugin's watch prints it to the new
  assignee's sessions for any assignment ("was assigned to your user by …; take it only when your
  user says so"), and tells a former assignee's sessions to stop (`describe` in `watch.py`). The
  focus `mine` filters it out: it lets through only Topics the session's Assistant holds or writes
  in (decisions 0022, 0024).
- **Correction (2026-11-11):** question 3 first said the sessions are woken only for a hand-over of
  a task in work; that was wrong, the watch already tells them of any assignment.
- **The decisions disagree on who assigns.** Decision 0031: "Any human of the Team, or an Assistant
  on their behalf, assigns; permissions come later." Decision 0032, "Who moves a task": "A human in
  the web plans: changes the order within a status by dragging and sets the assignee." Its
  rationale goes further: "ordering and assigning are planning and stay with humans". The server
  module's docstring says the same (`api/tasks.py`: "a human in the web plans: assigns and
  orders").
- **The web** sends the assignment as soon as the select changes (`TaskPanel` in
  `web/src/components/Task.tsx`); handing over a task in work asks for confirmation first.
- **The plugin:** `create_task` has `assignee` with the rule "only when your user says whose it
  is"; `list_tasks` filters by assignee; nothing else.

## What is needed

- An `assign_task` tool in the plugin: `task`, `assignee` (a pseudonym, or `-` to unassign, as
  `list_tasks` writes "unassigned");
  calls the existing endpoint; returns the task with its new assignee.
- The same rule as `create_task`: only when the user says whose it is.
- Decision 0032 (the rule and its rationale) and the module's docstring brought in line with 0031
  (an Assistant on its user's behalf assigns too), or the difference stated.

## Questions, one at a time

1. Does an Assistant hand over a task already in work (the former assignee's sessions are told to
   stop), or only assign tasks to do and unassigned ones, leaving hand-over to the web, where it
   asks first?
2. Assigning several tasks at once (a plan's new member has ten): one call per task, or a list in
   one call?
3. Is a person's own Assistant told when a task is assigned to them while they are offline (today:
   their sessions are woken only for a hand-over of a task in work)?

## Decided

- **Question 1 (the author, 2026-11-11): an Assistant hands over a task in work too, after its user
  confirms.** `assign_task` on a task in work held by another human is refused, naming the current
  assignee and that their sessions will be told to stop; the Assistant tells its user, and only
  after the user confirms calls it again with `hand_over=true`. The same shape as `take_task` with
  `reassign=true`, and the same question the web asks before a hand-over.
- **Question 2 (the author, 2026-11-11): one call per task.** No list in one call; the endpoint
  stays as it is, and a refusal concerns only its own task.
- **Question 3 (the author, 2026-11-11): the new assignee's sessions are woken by any assignment,
  with one line** ("Pavel assigned T-107 to you"), not only by a hand-over of a task in work. The
  Assistant does not take the task on its own; offline, the person finds it in their list and on
  the board, with no separate queue of what came while they were away.
- **Shipping (the author, 2026-11-11):** today, in one pull request with the turn count change
  (`2026-11-11-turn-count-with-a-human.md`).
- **Decisions 0031 and 0032 (the author, 2026-11-11): a clarification of 0032, not a new
  decision.** "A human plans" meant the human's decision, whether they set it in the web or through
  their own Assistant; 0032 gets a dated clarification, and the server module's docstring follows.
- **The focus `mine` (the author, 2026-11-11): it lets through the events about its user's
  tasks** — an assignment to them, a hand-over away from them, a task of theirs gone idle — as well
  as its Assistant's Topics; `quiet` stays quiet. Decision 0022 gets a dated clarification.
