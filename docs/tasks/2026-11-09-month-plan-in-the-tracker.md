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

## Questions

To be listed when the author takes the work up.
