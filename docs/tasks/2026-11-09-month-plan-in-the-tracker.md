# A month plan in the tracker: what was missing

## What happened

2026-11-09, the prototype team tried to move its approved month plan into the tracker. The plan has
four promises to users with dates, 24 deliveries (a delivery is a dated result for a named audience;
deliveries add up to promises), the tasks that provide each delivery (one to nine per delivery),
team work that serves no promise, and an "off-plan" section: work that displaces planned work, each
row naming what is dropped from the plan. Six questions in, the author stopped: "I don't like the
picture we are getting; Coloqo lacks the features to move the plan now. We'll come back after I add
them and go through all the questions again."

This file lists what the first pass ran into, as input for that work. Nothing here is decided.

## What the first pass ran into (plugin 0.8.0, 2026-11-09)

1. **A delivery has no place of its own.** Tried first as a field of the task — breaks on deliveries
   with several tasks; then as a sub-promise under the promise — works, but turns every promise into
   a goal and a delivery into a promise with the promise workflow.
2. **A task's parent cannot change** — a parent is set only at creation. Tasks created earlier from
   task Topics cannot be put under their deliveries; re-creating them splits the timeline.
   `docs/tasks/2026-11-09-change-a-tasks-parent.md`.
3. **A promise holds promises or tasks, never both.** A promise that holds deliveries cannot also
   hold an off-plan task that works for it; the task has to go under some delivery or nowhere.
4. **No off-plan and found-during-work marks.** The team's rules separate planned work, work found
   while making a delivery (within a time budget the delivery declared), and off-plan work with
   "what is dropped from the plan". Coloqo has no mark for either; the only place was a first line
   of the description.
5. **Tasks cannot be planned for people not yet in the Team.** Two newcomers have half of the
   month's tasks; the plan could not assign them until they log in.
6. **A delivery's own data has no field:** for whom, what the person gets, the planned date (never
   rewritten) and the actual date, a shift with its reason.
7. **Team work outside promises** (analysis, onboarding, internal fixes) is the same backlog as
   everything else; nothing says "planned for this month".

Item 2 is done: decision 0034, PR #29 (server 0.11.0, plugin 0.9.0).

## Questions, one at a time (listed 2026-11-09, evening)

1. **Where a delivery lives** (item 1): a sub-promise, as tried (a promise of deliveries becomes a
   goal, a delivery takes the promise workflow); a task type of its own, "delivery", between a
   promise and its tasks; or a line of a task (breaks on deliveries with several tasks).

   **Answer (author, 2026-11-09): a delivery is a field of the task, and other tasks are linked to
   it.** A delivery has nothing but its product statement, written by rules of its own, in a style
   of its own — the task's "product delivery line" decision 0031 left for later, beside the
   technical description. A delivery a few tasks work for is stated in one task, the largest or the
   central one; its subtasks work for it without a mark; another task with no delivery of its own
   is linked to it: "works for the delivery of T-12". Not taken: a task type "delivery" ("too
   much"), and a delivery as a grouping of its own (a new concept with its own pages and rights).
   Rules proposed with it: the link points only to a task that states a delivery; a task working
   for another's delivery states none of its own, so no chains. A promise's deliveries are then its
   tasks that state one, each with the tasks linked to it.
2. **Off-plan work that serves a promise** (item 3): the rule "a promise holds promises or tasks,
   never both" (decision 0031) against a task that works for a promise holding deliveries.

   **Answer (author, 2026-11-09): settled by answer 1, no change to the model.** With the delivery a
   field of the task, a promise holds tasks directly — deliveries' central tasks, the tasks linked to
   them and off-plan tasks — and no sub-promises are left in a month plan; decision 0031's rule
   binds only a goal. An off-plan task goes right under the promise it works for; question 3's mark
   says it is off-plan.
3. **The plan's marks** (item 4): planned, found while making a delivery (within the time budget
   the delivery declared), off-plan with "what is dropped from the plan" — a field of the task, and
   which values.

   **Answer (author, 2026-11-09): a plan is an entity, and the marks belong to a plan.** A task's
   life crosses plans: planned in one month and not done, carried into the next, done off-plan in
   the third; what it is, it is relative to a given plan. First proposed: a field of the task. The
   author: a field whose changes go to the task's timeline (decision 0033) keeps that history too —
   so the choice was not about history but about whether the plan is an object of the Team's work.
   It is: the month plan is approved, worked by and reviewed at the month's end, and off-plan work
   must name what it drops. So a light entity: the Team, a period, the moment of approval, and rows
   of membership, each with the mark and the "what is dropped" line; no workflow or Topic of its
   own. Membership is not hierarchy: a task has one parent, and may be in several plans. Every
   join and mark also goes to the task's timeline.

   Questions it opens, in its place:

   - **3a. What a plan holds**: promises, tasks, or both.

     **Answer (author, 2026-11-09): both.** Promises are what the Team promised for the period;
     tasks are the work, each with its mark. A promise added to a plan brings its tasks of that
     moment; a task that later appears under a promise of the plan joins the plan by itself (with
     the mark of 3b). A task with no promise joins on its own: the Team's work outside promises
     (question 6, likely settled by it).
   - **3b. The moment of approval**: before it everything added is planned; after it, found or
     off-plan, so the mark need not be set by hand.

     **Answer (author, 2026-11-09): the soft way.** A plan is a draft until a human, not an
     Assistant, approves it; who and when is kept. Before approval whatever joins is planned.
     After it the mark sets itself: found when the task has a `source` that is in the plan,
     off-plan otherwise. An off-plan task without "what is dropped" is not refused — tasks join by
     themselves when an Assistant creates them under a planned promise — but shown in the plan as
     unfinished, "what is dropped: not named", for a human to fill. A human may correct a mark
     (found ↔ off-plan), kept in the task's timeline. Not taken: the strict way (after approval a
     task joins only by a human's act, the line required), which would leave the tasks an
     Assistant creates under a planned promise outside the plan until a human adds them.
   - **3c. Carried tasks**: "carried from the previous plan" as a mark of its own, or read from
     "was in the previous plan, not done".

     **Answer (author, 2026-11-09): read, not marked.** A mark tells how work came into this plan:
     by the plan, found on the way, or displacing planned work; being carried is the task's history,
     not a way in. A task taken into the next plan's draft is planned there, as everything before
     approval; the plan shows "from October" beside it, read from the kept membership of the
     previous plan where it was not done. Carried after approval, it is off-plan by 3b.
   - **3d. A plan's result**: what counts as done in a plan, and what happens to the rest when it
     closes.

     **Answer (author, 2026-11-09):** done in a plan is a task finished (Done; a promise Delivered)
     by the end of the plan's period; cancelled and withdrawn are counted apart. A human closes the
     plan after its period, not the server by itself. Closing fixes each row's result (done,
     cancelled, not done), so work finished later does not rewrite the month. The rest goes nowhere
     by itself: it stays in the closed plan as not done and is carried by joining the next plan
     (3c); a new plan's draft may offer the previous plan's unfinished work. The result shows
     planned done and not done, found and off-plan counts, the list of what off-plan work dropped,
     and the promises with Delivered or Not delivered.
4. **Planning for people not yet in the Team** (item 5): an invitation that can be assigned before
   its person logs in, a planned assignee as text, or waiting until they log in.

   **Answer (author, 2026-11-09): wait until they log in.** Their tasks stay unassigned and the
   plan shows them so; they are assigned once the person is in the Team. Not taken: a named
   invitation that tasks can be assigned to, and a planned assignee as text.
5. **A delivery's own data** (item 6): for whom, what the person gets, the planned date (never
   rewritten), the actual date, a shift with its reason — fields, timeline entries, or both.

   **Answer (author, 2026-11-09): a delivery has no data of its own, and tasks get no dates.** A
   delivery is the way to tell the business what value the task gave: the task's meaning put into
   the business's language. Dates and the rest are attributes of the task, and decision 0031 stands:
   no due date on tasks. The author: "a way to leave empty promises behind. All of IT is built on
   lying to please the business; nobody hits the dates. Ours is a date computed from the speed of
   each member of the Team. If you want a delivery done sooner, there is the priority mechanism.
   That is honest." So the forecast date comes later, with the estimates and speed coefficients
   (questions 11–16 of `2026-11-08-speed-coefficients-and-a-task-tracker.md`); priority is the
   order (decision 0031). The plan's period and the moment a task reaches Done are the dates there
   are. The found-work budget waits for estimates too. First proposed and not taken: a planned date
   on the delivery, then in the plan's row, then on the task, each with shifts by reason.
6. **Team work planned for the month outside promises** (item 7): a period on any task, a
   promise-like container for the month's own work, or a mark.

   **Answer (author, 2026-11-09): settled by 3a.** "Planned for this month" is membership in the
   plan: a task with no promise joins on its own, planned if it joined before approval. The plan
   shows such tasks as a group "outside promises", beside the promises and their tasks.

## Settled (2026-11-09)

- **The delivery** is a text field of the task: the task's meaning in the business's language,
  written by rules and in a style of its own. A task with no delivery of its own may be linked to
  one that states it: "works for the delivery of T-12". The link points only to a task that states
  a delivery; a linked task states none; a task's subtasks work for its delivery without a mark.
- **No dates on tasks** (decision 0031 stands): the forecast comes from each member's speed, later;
  priority is the order.
- **The plan** is a light entity of the Team: a period, a draft until a human approves it (who and
  when kept), closed by a human after the period. It holds promises and tasks; a promise added
  brings its tasks of that moment, a task later created under a planned promise joins by itself,
  a task with no promise joins on its own.
- **Marks** belong to the plan's row: planned (joined before approval), found (after approval, its
  `source` in the plan) or off-plan (after approval, otherwise), set by themselves; a human may
  correct found ↔ off-plan. Off-plan work names "what is dropped"; until it does, the plan shows it
  as unfinished. Every join, mark and line goes to the task's timeline.
- **Carried** work is read from the previous plan, not marked.
- **Closing** fixes each row's result (done, cancelled, not done); unfinished work stays there and
  is carried by joining the next plan, whose draft may offer it. The result shows planned done and
  not, found and off-plan counts, what was dropped, and the promises' outcomes.
- **Newcomers' tasks** wait unassigned until they log in.

## To settle before the plan's code

- **"Found" by a `source` the server filled in** (a side review, 2026-11-09). By 3b a task
  joining after approval is found when its `source` is in the plan. But `source` is not always
  set on purpose: when an Assistant gives none, `create_task` fills in the task whose Topic the
  session holds, if exactly one. An Assistant working on planned T-12 that files an unrelated,
  urgent task would make it "found", and nobody would name what it drops — the very case the
  Team's rule is there to catch. One way out: found only when the `source` was given explicitly.

  **Answer (author, 2026-11-10): found only by an explicit `source`.** The server keeps whether the
  caller gave the `source` or the server filled it in; a filled-in `source` still tells where the
  task came from but does not set the mark — such a task joins off-plan and asks for "what is
  dropped".

## Settled while writing decision 0037 (2026-11-10)

A side review found that the first draft of decision 0037 recorded forks the author had not
decided; they were asked:

- **"What is dropped" is written by a human only** — a conscious choice; the empty line stays the
  signal. An Assistant does not fill it, so it cannot write something plausible to silence it.
- **An Assistant creates a plan and fills its draft** (the first move of the month plan was the
  lead's Assistant). Approving and closing are a human's; after approval work is added explicitly by
  a human, and tasks under planned work join by themselves.
- **A task leaves a plan only while it is a draft**, and not every task: one not started, always;
  a started one, only before the plan's period begins; a finished one, never. The plan is not
  strict, but work under way in its period stays in it and in its result.
- **A Team's plans do not overlap in time**; the server refuses an overlap. A task has one promise
  (decision 0031); it is in several plans one after another (carried), never in two at once. A plan
  of a larger period around the monthly ones (a quarter) holds plans or the quarter's promises, not
  tasks: a decision of its own when it is needed.
- **A row may be postponed** (the author, 2026-11-10): a task in a plan is put off in favour of
  off-plan work, or because its time was misjudged — it is not removed but stays in the plan and is
  not done in this period. Postponing is a state of the row, not the task; its reason is required
  ("in favour of T-57", "misjudged, no time"); a human postpones and may undo it; it goes to the
  task's timeline. At closing a postponed row not done is "not done" and counted apart as
  postponed; done anyway, it is done. In a draft whose period has begun a started task cannot be
  removed but can be postponed. The off-plan task's "what is dropped" and the postponed task's
  reason name each other as text; neither is derived from the other. Lowering priority stays the
  board's order.
