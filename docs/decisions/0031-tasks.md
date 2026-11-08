# 0031. Tasks: a tracker in Coloqo

**Date:** 2026-11-08 · **Question:** the author wants a task tracker in Coloqo: an Assistant opens
a Topic under a concrete task, tasks move by stages on a board, and a Team's developers keep their
daily tasks here while large ones stay in the external tracker · **Refines:** decisions 0006,
0015, 0021, 0023, 0025; product statement W4 and question 4

The prototype team keeps large tasks in its external tracker, where they move about once a week; the
tracker at the developers' hands is to be Coloqo. Measuring each person's speed (the working file,
§1–3) showed that only Coloqo's Topics hold the real timeline of a task, and that a tracker in
Coloqo would make that measurement a report instead of research. Product statement W4 (2026-10-17)
had ruled out a task board of Coloqo's own. The working file is
`docs/tasks/2026-11-08-speed-coefficients-and-a-task-tracker.md`, questions 1, 2, 5, 9 and 10.

Workflow, stages and boards are decision 0032; the timeline and whose move, decision 0033.

## Decision

### Coloqo and the external tracker

- **Coloqo is the system of record for a Team's working tasks**; the external tracker stays the
  system of record for what the Team keeps there.
- **A link to an external issue is its key and URL**, with no sync and no Team credentials on the
  server. A task has any number of links; an external issue may be linked from several tasks.
  Duplicating an issue and breaking it down are the same link.
- **The bridge is the Assistant, not the server, now and later.** It moves the external issue with
  its own tools and its human's rights when the Team rules ask ("when a task linked to an epic
  closes, comment its outcome there"), and imports ("move epic ACME-42 into a promise") by reading
  the external tracker and creating tasks. No server integration on the cloud instance; on a
  self-hosted instance it may come one day as a paid feature (M1).
- **The tracker is the Team's choice.** Of W4 this reverses only "why not our own task board"; the
  reasons against a server integration stand. The Workers' queue by a tracker filter is left for
  when Workers are built.

### Task and Topic

- **A task is an entity of its own; a Topic refers to it** by a nullable task id. The model allows
  many Topics per task; the first version allows one, by a unique index. Assistants lean to
  bureaucracy and would open Topics by classifications of their own; one long feed is easier than
  many short ones. Lifting the limit is dropping the index; a "main Topic" mark comes only then. A
  side question to a colleague goes into the task's Topic, addressed to that person (decision 0029).
- **The data and the presentation are separate.** While a task has one Topic, the web shows them
  as one thing with one name.
- **A Team without the tracker has tasks too.** A Topic opened for a task gets a task, created by
  `open_topic` itself; its stages move by a built-in workflow (decision 0032); the workflow editor
  and the board are off. Turning the tracker on is a switch, not a migration.
- **Free Topics.** A Topic that is not anyone's work item has no task and lives in the permanent
  section "Free Topics" of its Area. In the data it is no row of its own: Topics with no task. A
  free Topic that grows into work becomes a task's Topic.

### Names and numbers (refines decision 0025)

- **The letter `T` goes to tasks**: `T-42`, `/team/acme/task/42`, a Message `/team/acme/task/42#m-5`,
  another Team's `globex/T-42`; numbered per Team from 1 without gaps. Moving a task between Areas
  does not change its number.
- **A task's Topic has no number of its own.** It opens at `/team/acme/task/42`, where the web shows
  the task and its Topic as one, and at `/team/acme/task/42/topic`; with several Topics later, the
  next ones are `/team/acme/task/42/topic/N`.
- **A free Topic is `F-5`, at `/team/acme/topic/5`**, another Team's `globex/F-5`, numbered by a
  counter of the Team's own. A number is given once and never again: a free Topic that becomes a
  task's Topic leads there by its former name and address (`/team/acme/topic/5` →
  `/team/acme/task/47`), so the list of free Topics may show gaps, as file numbers do (decision
  0025).
- **Existing Topics, at the migration, are free Topics that became tasks with the same numbers**:
  tasks of a Team without the tracker, an open Topic in progress, a closed one done. Both of a
  Team's counters, tasks' and free Topics', continue after them; a new Team starts both at 1. So
  every `T-12` in an MR or an issue keeps its meaning, the full links `/team/acme/topic/12` (and
  `#m-5` in them) that the briefing asked Assistants to write there lead to `/team/acme/task/12`,
  and the API calls of plugins not yet updated (decision 0027) resolve there by the same rule — one
  rule for resolving a number, no separate redirects. (The old links were pointed out by a review
  note on 2026-11-08; the author proposed keeping `/topic/N` for free Topics.)
- **The plugin's tools take both forms.**
- **A Team key** (`ACME-42`) may come later as a setting, a second name; the short form always
  works.

### Fields

A task has a **type** (task or promise), **title**, **description** (Markdown, with history,
decision 0033), **stage** (decision 0032), **assignee**, **Area**, **parent**, **external links**,
**outcome**, **order**, and **estimates** as timeline entries. The title, description and outcome
live on the task; its Topic shows them. A free Topic keeps its own title and outcome.

- **The assignee is a human.** An Assistant and a Worker are the human's tools. A task a Worker does
  is assigned to its responsible human. A Worker may still hold a Topic (decision 0015): the holder
  acts, the assignee answers for it. To be reconciled with decision 0015 when Workers are designed.
- **An assignee may be set in any stage**, the backlog included: assigning is planning. Any human of
  the Team, or an Assistant on their behalf, assigns; permissions come later.
- **A task with no assignee is assigned by its first move into work** to the human on whose behalf
  the move is made. A task assigned to another human is taken only by an explicit reassignment.
  Later moves do not change the assignee. There are no co-assignees.
- **A task in work may be handed over** by a human in the web, e.g. when its assignee is ill
  (the author, 2026-11-09): the web asks first; the former assignee's sessions are told to stop
  and the new one's to take it with `take_task`; the former holder of its Topic can no longer
  close it.
- **Creating a task is an event** with its author and its source: the task within which it was
  created, usually the one whose Topic the session holds. A task with a source was found during
  the work; one without, planned.
- **Order within a status** stands for priority: what is higher matters more. No priority field, no
  due date on tasks, no assignee's own estimate in the first version. Labels come later, for
  groupings without an end (a client, a component).
- **An estimate** is a timeline entry: hours, a breakdown, its kind (early or full), the estimator's
  version, author and date. Who estimates and where is the next feature.

### Promises, goals, subtasks

- **A promise is a task of the type "promise"**: a commitment for a period that tasks work towards,
  in product terms. It has a Topic, an outcome, external links, a timeline and a `T-` number.
- **A promise holds either promises or tasks, never both.** A promise that holds promises is called
  a **goal** in the web; it is not a type of its own. When a promise gets its first sub-promise, its
  tasks are moved into sub-promises first, or the server refuses. The depth is not limited.
- **A task holds only subtasks; a subtask holds nothing.** A subtask is a full task with a parent
  task. A parent's stage is not derived from its subtasks. When to make a subtask is a rule for
  Assistants in the Team rules, not the model.
- **A task may stay outside promises.**
- **A promise's fields**: a period (a start and an end date) and the human answering for it.
  Computed, not stored: the sum of its tasks' estimates, progress by tasks and by estimated hours,
  and its deliveries once a task's delivery line exists. A goal's progress is counted over its
  promises.
- **What a promise holds may live in any Area of the same Team**, never another Team's. Every task,
  a promise included, has exactly one Area; it is listed there and takes its workflow through it
  (decision 0032).

## Why

- A Topic per task (decisions 0006, 0021, 0023) already gives the timeline; a task gives it a
  stage, an assignee and a place on a board, and outlives the conversation.
- Keeping the task and the Topic apart in the data and one in the web lets many Topics per task,
  a Team without the tracker and a later switch to the tracker come without migrations.
- The levels follow the author's practice and the common shape of known methods (Jira's initiative
  → epic → story → sub-task, SAFe, OKR): product above (goals, promises), technical below
  (subtasks), the task as the seam that states its delivery in product terms. The rule "promises or
  tasks, never both" is the author's from the external tracker, where it kept the hierarchy from
  turning into hell.
- A promise as a task type rather than a separate group reuses the Topic, outcome, links and
  timeline; Jira's epics and GitLab's and GitHub's work items went the same way.
- `T` for tasks: in the web a task and its Topic are one thing, so they share a name; `F` shows a
  free Topic at once. A key on the Team, which tasks do not leave, never renumbers; Jira, Linear and
  ClickUp key by a project, team or space and renumber a task moved out of it.
- The assignee is a human because responsibility is always a human's; recording each event's
  author keeps a Worker's output from silently inflating its human's figures.
- The bridge through the Assistant costs no server code and has no sync to break on diverging
  workflows; large external issues move about once a week, and an Assistant updating them is
  enough.
