# 0032. Workflow, stages, statuses and boards

**Date:** 2026-11-08 · **Question:** how a task of the tracker (decision 0031) moves, who moves
it, and how a board shows it · **Refines:** decision 0021

The external tracker lets a team define its own workflow and give one project several boards; the
author asked not to copy all of it but to build so that Coloqo can grow there without pain. The
measurement of speed (the working file, §1–3) reads a task's stages, so "to do → in progress → done"
is not enough. The working file is `docs/tasks/2026-11-08-speed-coefficients-and-a-task-tracker.md`,
questions 3, 4, 6, 7 and 10.

## Decision

### Terms

What moves is a task's **stage**: analysis, design, code and so on. A **status** is a Team's
grouping of stages, shown as a column of the board: there are too many stages to see on a board.
The Assistant moves the stage; the status follows.

### Where a workflow lives

- **A workflow is a row of the Team; an Area points to one**, and a task finds its workflow through
  its Area. Several Areas may share one.
- **The first version shows one workflow per Team** for tasks, plus the promises' own: every Area
  points to it, one editor. A workflow of an Area's own later is a second row and a changed pointer;
  moving a task between Areas with different workflows will need a mapping of stages.
- **Workflows by task type**: tasks and subtasks share one, promises have their own. The
  measurement reads only tasks and subtasks.

### Stages

- **A stage has a kind** from a fixed set; the measurement, boards and reports read the kind, never
  the name. A Team names its stages and may add its own, each of one kind.
- **The kinds of a task's stages:**

  | Category | Kind | What happens |
  |---|---|---|
  | to do | backlog | written down; may have no assignee |
  | in progress | analysis | a person asked an Assistant to take the task: their time starts |
  | in progress | design | a plan of changes with forks; the human approves it, often step by step |
  | in progress | documentation | the documentation changes, as an MR when the docs live in git |
  | in progress | agreement | the decision goes to the Team or the lead; the docs MR is reviewed and merged when there is one |
  | in progress | code | the code, in one or several repositories |
  | in progress | review | the MR and its review rounds |
  | in progress | delivery | the release and the check in prod |
  | finished | done | verified in prod |
  | finished | cancelled | closed without a result; not counted as work done, the time spent stays visible |

  "Before code" is analysis to agreement; "code → prod" is code to delivery.
- **The built-in task workflow** has one stage per kind: Backlog → Analysis → Design →
  Documentation → Agreement → Code → Review → Delivery → Done, and Cancelled. A Team without the
  tracker moves by it too.
- **The built-in promise workflow:** Draft (to do) → Given (in progress) → Delivered, Not delivered
  or Withdrawn (finished). "Not delivered" is a miss against the period, "Withdrawn" a decision; a
  partial delivery is told in the outcome. An undelivered promise is not extended: a new one is
  given for the next period and the unfinished tasks move into it.
- **Moves are free within work**, back ones included (review → code). **The finished stages are
  final**: a finished task or promise is not reopened; a fix is a new task, and mentioning `T-42` in
  its description is enough — no relations between tasks.
- **A stage may be passed at once with a mark**, "skipped: no documentation changes"; the timeline
  keeps it, so "there was no such stage" differs from "it took 0 minutes".
- **A wait is not a stage** but a mark over any stage (decision 0033).
- **The Team's owner edits a workflow in the web.** Renaming and reordering are free. Removing a
  stage that has tasks asks where to move them; the history keeps the old name and kind. Only
  backlog and done are required.
- A graph of allowed moves comes later, as rows.

### Who moves a task

- **Only an Assistant moves a task**, and of the Assistants only the assignee's: moving it is work,
  done with notes, skip marks and the outcome. Another Assistant writes in the Topic. A human in the
  web neither moves stages nor closes tasks; they ask their Assistant. A human may still close a free
  Topic in the web.
- **A human in the web plans**: changes the order within a status by dragging and sets the
  assignee.
- **The Assistant's actions:**

  | When | Action | What happens |
  |---|---|---|
  | work found along the way | create a task | backlog; the source is the current task |
  | a human asks to take a task | take the task | to analysis, assigned if no assignee, its Topic opened and held, in one action |
  | new work with no task (a Team without the tracker) | open a Topic for a task | the task is created in analysis |
  | the next step | change the stage | possibly with "skipped: reason" |
  | done or cancelled | close the task | done or cancelled, with an outcome |

- **A change of stage replaces the free-text stage note** of decision 0021 in a task's Topic: the
  event keeps the kind and, if wanted, a line of comment. Progress notes stay.
- **Closing a task closes its Topic**; the outcome is required. A Message in a finished task's Topic
  may be written and changes nothing in the task.
- **Tasks are not closed for inactivity**: that would write a false outcome. A task in work with no
  activity (no timeline event, no Message in its Topic) gets a notice to its assignee's sessions
  after 7 days, then every day until something happens; a task with an active wait gets none. The
  threshold and the repetition are Team settings (added 2026-11-08 with the implementation plan). Free Topics keep decision 0021's rule.

### Boards

- **A board is an entity of the Team**: ordered columns, each a set of stages or a condition. A
  task's status is the column of the Team's main board it stands in. More boards later are more
  rows; a board's filter by labels may keep, e.g., planning tasks off the working board.
- **The first version shows one board per Team**, with built-in columns "To do" (backlog), "In
  progress" (analysis to delivery), "Done" (done, cancelled); the owner edits the columns.
- **A "Waiting" column** is a column by the condition "has an active external wait": a task with
  one stands there whatever its stage and returns when the wait ends. Only explicit external waits
  go there; a wait inside the Team shows on the card as whose move it is. The built-in board has no
  such column; the owner adds it.
- **A card shows** the number, title, assignee, stage, promise, whose move it is and, when waiting,
  what is awaited ("Code · waiting: a token from the infrastructure").
- **Tasks and subtasks are on the board**; a subtask's card shows its parent. **Promises are not**:
  they have a tree view of their own with their tasks and progress.
- **Filters** by Area, assignee and promise are parameters of the view; a link keeps them.
- **"Done" shows the last two weeks**; the rest are in the list and search.
- **A Team without the tracker** has the board hidden, and no planning: creating a task in the
  backlog and assigning are refused with "turn the tracker on"; taking, moving and closing work as
  with it (added 2026-11-08 with the implementation plan).

## Why

- Kinds apart from names let a Team rename and split stages without breaking the figures; columns
  apart from stages let boards differ without touching tasks.
- The stages are the prototype team's process as the author described it; the measurement needs the
  border between "before code" and "code → prod", where raw and prepared tasks differ (the working
  file, §1.4).
- A wait as a stage would erase where the task stood; as a mark with a column by condition, the
  board shows it and the stage stays.
- The Assistant does the work around a move, so the move goes through it; ordering and assigning are
  planning and stay with humans.
- Final finished stages and mentions instead of relations keep the tracker from drowning in
  bureaucracy.
