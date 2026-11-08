# Speed coefficients from Topics, and a task tracker in Coloqo

## Why this file

In early November 2026 the prototype team (three developers, two newcomers about to join, and a
lead) planned its month person by person: how many hours of each person's month the planned tasks
will take. For that it measured a speed coefficient per person, and one of its sources of fact was
the team's Coloqo Topics. The measurement worked, but the Coloqo part of it was done by hand.

The author wants measuring coefficients to become an ordinary thing that happens inside Coloqo,
and proposes to add a task tracker to Coloqo for that. This file records the method as it was
actually run, says what Coloqo gave and what was done by hand, and lists the questions for
designing the feature.

**Status (2026-11-08):** the tracker's questions (1–10, 9a) are settled and written down as
decisions 0030 (Topics are kept), 0031 (tasks), 0032 (workflow, stages and boards) and 0033 (the
timeline and whose move). Estimates and coefficients (questions 11–16) are deferred to the next
feature.

## The principle: figures are a mirror (the author, 2026-11-08)

**Figures are a mirror for the person themselves and material for the Team's conversation, not an
instrument of oversight.** Everything Coloqo measures about work — coefficients, whose move, the
cost of parallel sessions — exists so that a person sees their real figures and the Team has facts
to work on its efficiency with; never for watching or control in the bad sense. Every question
below about what is measured, kept and shown is decided inside this frame.

## 1. The method as run (2026-11-03 … 2026-11-05)

### 1.1 Quantities

- **Estimate** — a model, blind, estimates a task in working hours of *a developer with an AI agent
  following the team's full process* (read the canon, change it, code, an MR with review rounds,
  release, journal entries). The estimate is a unit of work, not a promise of time.
- **k = fact / estimate** — the share of the estimate a person actually spends.
- **Speed = 1 / k** — how many estimate-hours a person closes in one working hour. The lead asked
  to show speed next to k: "faster" reads better than "smaller".

The model's estimate is the common yardstick: it is applied to finished tasks (calibration) and to
next month's tasks (planning) the same way, so k carries a finished month's pace into the next one.

### 1.2 The blind estimator

- **Inputs are scrubbed.** The task text goes to the estimator without dates, assignees, issue keys
  or anything that hints how long it took. Tasks from different people are mixed in one batch.
- **Two passes per task:** the *early* description (as the task was first written, often "raw")
  and the *full* description (after elaboration, what the task became). The calibration used the
  mean; the month plan later used the early pass only (§1.5), because the new tasks were not
  elaborated yet and k has to be measured on the same kind of text it will be applied to.
- **The estimator answers with hours and a breakdown** (canon — 3 h, service A — 4 h, review
  rounds — 5 h …), so a strange number can be read, not just accepted.
- **Fixed setup.** The same instruction text and the same model for calibration and planning;
  otherwise months are not comparable.

### 1.3 Fact — four sources

The team measured the fact four ways and compared them.

1. **Coloqo Topics, throughput of a window.** The window runs from a person's first Topic mark
   ("took the task") to the last ("verified in prod by the pods"); fact = working hours in the
   window (8 h per working day); work = estimates of tasks done in the window (a partly done task
   counts by its share). Summing the durations of Topics would be wrong: while one task waited for
   the lead's answer or an account, the person did another one. The window absorbs that overlap.
2. **Tracker + code host, whole available period.** Units are the issues the person closed in the
   period (subtasks under their parent) and their merged MRs, including MRs without an issue; fact
   = working days of the period × 8 h. Code merged in one month and the issue closed in the next
   was split between months.
3. **Activity days.** Each working day (8 h) is split between the tasks with the person's activity
   that day: a commit weighs 1, creating or merging an MR and a comment 0.3, a status change in the
   tracker 0.1; days without activity are spread in proportion. This gives a fact per task, not
   only per window.
4. **Coloqo per task: before code and code → prod.** For one developer's three tasks the Topic
   timeline was split at the moment code started: time on forks (questions to the lead, waiting for
   answers, reading the canon) and time from the first code to prod.

### 1.4 What came out

- **The methods agree.** For each developer the three per-window methods differed by less than 0.1
  in k; developers' k fell between 0.3 and 0.52 (speed 1.9–3.3). The lead's k, from the tracker and
  code host only: 0.16 in September, 0.14 in October (speed 6.3–7.2) — with management, meetings
  and several parallel agent sessions in the same hours.
- **Early-description k is higher than full-description k** (0.45 vs 0.31 for one developer, 0.48
  vs 0.39 for another): an early text undersells the work, and the estimator sees less of it.
- **Raw and prepared tasks are indistinguishable by commits and tracker events** (method 3), and
  clearly different by Coloqo (method 4): on raw tasks k ≈ 0.45–0.5, on prepared ones ≈ 0.3. On the
  largest raw task the code-to-prod part alone had k ≈ 0.24; as much time again went before code.
  The reason is the source: commits and tracker events see code; forks, questions and waits leave
  no trace there and smear over neighbouring tasks. Only the Topic timeline showed them. Three
  tasks are a pointer, not a measurement.

### 1.5 Planning a month with k

- **Load = Σ (estimate of the person's planned tasks) × k / capacity.** Capacity = working days of
  the month from the planning date × 8 h, minus days off and late starts (the newcomers from the
  9th; the lead minus the last days of the month reserved for planning the next one).
- **Newcomers get a forecast k** from the lead's judgement ("about like developer X", "a bit slower
  than Y, +10–15 %") until their own month is measured.
- **Fill to 70 %.** The lead's rule: plan each person to 70 % of capacity, keep 30 % for hot work of
  the month's main direction.
- **People work gets k = 1.** The lead's own k was measured on his code and canon; for mentoring
  and leading he decided k = 1 (an estimated hour of work with people is an hour). His month came
  out at 130–140 %; he took the risk knowingly, with the developers' 30 % reserve as the buffer.
- **Estimator drift by anchors.** Nine calibration tasks with known estimates were mixed into each
  new estimation batch, shuffled. Drift = Σ new estimates of anchors / Σ old ones; new tasks are
  divided by the drift to bring them to the calibration's scale. Four batches on the same day gave
  drifts 0.86, 0.85, 0.96 and 1.07: the estimator itself wanders by about ±10 % between runs, and
  without anchors that noise would read as a change in people's speed.

### 1.6 Decisions the lead made on the way

- Measure coefficients monthly and watch how they change; the aim is to work as fast as possible
  without losing quality.
- Estimate each task with the model before and after elaboration, and write both estimates into
  the task's description.
- Do not elaborate tasks deeply for the developers: working out the forks is where they learn;
  it pays off in the long run even if it is slower now.
- Measurements are shown as a separate page for discussion at the daily; the method is worked out
  by the team, not handed down.

### 1.7 Limits the team named

- 8 working hours a day is an assumption; Topics show work in the evenings and at weekends.
- The tracker's assignee is the current one; issues without an assignee fall out of the sample.
- Large stories without an MR were estimated from text only (±50 %).
- The estimator weighs text: a detailed story full of forks "weighs" more, though the detail is a
  result of the analysis, not of the amount of code.
- The lead's denominator holds management too; his k is not a pure development speed.
- Small samples: a few weeks per developer, about ten tasks in the Coloqo methods.

## 2. What Coloqo gave, and what was done by hand

### Gave

- **A timeline of each task with times.** One Topic per task, stage notes, questions and answers,
  "merged", "verified in prod by the pods", the closing outcome. No other source had the start of
  work on a task and its real end (prod, not the merge).
- **Waits as facts.** "Asked the lead 15:27 — answer 16:20", "waiting for CI and the merge", "an
  account request is out". This is what split *before code* from *code → prod* and made raw and
  prepared tasks distinguishable at all.
- **Overlap made visible.** Several held Topics at once showed that a person worked on another task
  while waiting; that is why the window, not the sum of Topic durations, is the right fact.

### Done by hand

- **No export was involved.** The measurement script that "builds the Topic timeline" does not call
  Coloqo: the model read the Topics and wrote the events and waits into the script as ready text
  ("question to the lead", "answer", "waited for CI — reason not named"). The Coloqo numbers are
  the model's reading of conversations, not data.
- **Stages are free text.** "Studying the canon", "canon/MR/rounds", "[subtask] implementation
  started" — each had to be interpreted into *before code / code / waiting / in prod*.
- **Waits have no start and end marks.** The end of a wait was inferred from the next event; the
  waiter and the reason were often not named.
- **Subtasks live inside one Topic** with a bracketed prefix in the text; attributing time to a
  subtask was guessing.
- **Retention ate the history.** On the cloud instance a closed Topic loses its Messages after 7
  days (decision 0021): tasks closed before the window had only cards with an outcome, no stages.
  A monthly measurement cannot be collected from a 7-day archive.
- **Times have no zone in what the Assistant reads;** the team verified they were local time by
  matching deploy times mentioned in the text.
- **Everything else came from elsewhere.** Estimates, assignees, close dates and units of work came
  from the tracker and the code host through their REST APIs; capacity (days off, other projects,
  late starts) lived in nobody's system — in the lead's words in a chat.

## 3. What a measurement needs from Coloqo — whatever the tracker question decides

These follow from §2 and do not depend on whether Coloqo gets its own tracker.

1. **Stage kinds from a fixed vocabulary**, with free text beside them: *elaboration*, *code*,
   *review*, *merged*, *in prod (verified)*, *done*. A Team may extend the list; the measurement
   reads kinds, not words.
2. **Waits as a pair of marks:** "waiting: whom / what" and "resumed", so a wait has a start, an
   end, a waiter and a reason.
3. **Subtasks as Topic parts,** not prefixes in text, so time attaches to them without guessing.
4. **A task's timeline outlives retention.** At closing, the card keeps the stage and wait marks
   with times (not the conversation), or the Team exports them. Cards already survive deletion;
   the marks are small.
5. **Times with a zone** in everything an Assistant reads.
6. **A person's calendar for capacity:** days off, part-time, days given to another project.
   Without it the denominator is "100 %, 8 hours", which is the largest assumption in the method.

## 4. The task tracker idea

The author's idea: a full task tracker inside Coloqo. Then the estimate, the timeline and the
capacity live in one system, and k is a report rather than a research project: at the end of a
month the Team sees each person's k and speed, how they moved, and the next month's load is
computed from the same records.

What such a tracker would hold for this purpose:

- **A task with its estimates:** early and after elaboration, each with the estimator's version
  (instruction text and model) and a date — the "before and after elaboration" rule from §1.6 as
  fields, not prose in a description.
- **The task's Topic** — already one per task (decisions 0006, 0021): the timeline comes for free.
- **An anchor set:** 10–15 finished tasks with known fact, re-estimated each month to measure the
  estimator's drift (§1.5).
- **Assignee history,** so a task is attributed to who did it, not to who holds it now.
- **The person's calendar** (§3, item 6).
- **A month plan:** planned tasks per person, capacity, the fill limit (70 %), and later the plan
  versus fact — what was planned, what was found during the work, what came out.

**It runs against a settled decision.** Vision question W4 (2026-10-17) says: "Why not our own task
board: it duplicates the tracker, and the system of record is the tracker"; and the server does not
integrate with the tracker, because it would need the Team's credentials, a corporate tracker is
unreachable from the cloud, and the Team's tasks would be stored with us (decision 0014). The idea
reopens that question; it is the first one to settle (§5, question 1).

## 4a. The author's proposal (2026-11-08)

The author, in their words (translated from the discussion):

- **Coloqo gets a full task tracker.** An Assistant opens a Topic not on an abstract question but
  under a concrete task: the task exists, and the Topic of reasoning moves under it.
- **A task's statuses become concrete.** They are defined in advance, the same for every task of a
  project. A board shows tasks moving through the statuses from left to right, as in any tracker.
- **A Coloqo task can refer to a task outside**: duplicate it or break it down. The prototype team
  keeps large tasks in its external tracker, where they move rarely, about once a week; the tracker
  at the developers' hands, with the daily tasks, is to be Coloqo.
- **Settle the minimum a tracker needs, and how plastic it can be.** The external tracker lets a
  team define its own workflow (statuses and the graph of moves between them) and give one project
  several boards that show those statuses differently. Coloqo does not copy all of it, but its
  architecture should let it grow there without pain.
- **Measuring speed coefficients** (§1–3) is the first use the tracker makes cheap.

### What plasticity asks of the data model (a sketch, not decided)

(Terms changed by question 6: what this sketch calls a status is a **stage**; a **status** is a
column, a Team's grouping of stages.)

The external tracker's plasticity comes down to a few separations. Kept in the data from the start,
they let the features come later as new rows, without migrating tasks:

- **A status is a row, not an enum:** a name, an order and a category from a fixed set (to do, in
  progress, done). Boards, reports and the measurement read the category; a Team names statuses as
  it likes.
- **A workflow is a set of statuses plus, optionally, allowed moves.** No moves listed means any
  move is allowed — the minimum; a graph comes later as rows.
- **A task points to its status, never to a column.** A board is a separate thing: columns, each a
  set of statuses, and a filter. One board first; more boards later are more rows.
- **A status change is an event with its time and author, kept with the task.** That is the history
  the measurement needs (§3, item 4), and it outlives a Topic's retention.
- **A workflow belongs to a scope** (the Team; later an Area or a task type); a task finds its
  workflow through the scope, so a second workflow later does not touch the first.

## 5. Questions — one at a time

What a task is comes before how it moves; the coefficient questions come after the tracker, since
they read its data.

### The tracker

1. **Coloqo as the system of record for working tasks, with external issues as links?** The
   author's proposal sets the direction; to settle: links without sync and without the Team's
   credentials on the server, a task with several links and an external issue with several tasks,
   whether the tracker is the Team's choice or replaces Topics with an issue key, and what of W4 it
   reverses.
2. ~~**Task and Topic.**~~ Decided (see Decided).
3. ~~**The scope of a workflow.**~~ Decided (see Decided).
4. ~~**The minimal workflow.**~~ Decided (see Decided); the discussion kept below. Statuses with categories and free moves; who edits it; what happens to
   tasks when a status is removed. The author (2026-11-08): the workflow is what changes on a task
   are seen and coefficients are computed by, so "to do → in progress → done" is not enough; the
   built-in minimal workflow, also the one of a Team without the tracker, is to be discussed on its
   own.
   - Proposed (2026-11-08, Claude): a fixed set of status kinds the measurement reads, with names
     and extra statuses left to the Team; free moves; a wait is a mark over any status, not a
     status. The author found "backlog → ready → elaboration → code → review → delivery → done" not
     enough, and "ready" unclear.
   - The author's stages (2026-11-08), in discussion:
     - **Backlog** — the task may have no assignee.
     - **Analysis** — done by an Assistant, but a person asked it to take the task, so from here
       the person spends their time on it.
     - **Design** — the Assistant has a plan of changes, usually with forks; even without forks
       the plan goes to the human for approval, most often step by step. After it there is a
       ready plan for the documentation and the code.
     - **Agreement** — the decision is brought to the Team or the lead; with documentation
       changes, both are agreed, without them only the decision.
     - **Documentation** — the changes are prepared, as an MR when the docs live in git. With no
       changes the stage is passed at once, with a mark "no documentation changes".
     - **Code** — in one or several repositories.
     - **MR and review rounds.**
     - **Delivery.**
     - **Done.**
   - **The order of documentation and agreement (2026-11-08, the author):** design →
     documentation → agreement → code. Documentation prepares the MR of the docs; agreement reviews
     and merges it when there is one, and agrees the decision alone when there is none.
   - Still open in question 4: passing a status at once with a mark ("skipped: no documentation
     changes") as a general mechanism for any status; a "cancelled" kind among the finished ones;
     who edits the workflow and what happens on removing a status.
5. ~~**Task fields in the first version.**~~ Decided (see Decided, parts 1–4); the discussion kept below. Title, description, status, assignee (a person; an
   Assistant; a Worker?), Area, external links, a parent task (subtasks, §3 item 3), estimates
   (§4). Numbering: a prefix of its own next to `T-` (decision 0025)?
   The author (2026-11-08): besides statuses, should the task log other actions, such as who it is
   assigned to? In the backlog a task may have no assignee, and every move is made by someone: is
   the task then assigned to them, or is "moved to this status by that person" enough? Unclear yet.
   - The assignee and the author of events: decided (see Decided, question 5, part 1). Numbering,
     title, description and outcome: decided (part 2). Subtasks: decided (part 3, with promises).
     Estimates and the other fields: decided (part 4). Question 5 is settled, but for the product
     delivery line, left for later.
6. ~~**Who moves a task, and how stages relate to statuses.**~~ Decided (see Decided). The Assistant through the plugin, a
   human in the web; does a stage note move the status, or are they separate (§3 item 1)?
7. ~~**Boards in the first version.**~~ Decided (see Decided). One per Team from the statuses, or
   boards as entities from the start; filters (Area, assignee).
   - **A "Waiting" column** (raised by the author, 2026-11-08), in discussion. The prototype team's
     board has one: a task depends on an outside team (e.g. the infrastructure) and waits for work
     or a decision beyond the Team's reach — the Team did its part and waits. Examples: an
     integration with an external system needs, besides the code, a token issued by the company's
     process, and with its side done the Team waits for it; or the code of an integration waits
     for the external system's specification. How does it fit a scheme where a wait is a mark over
     a stage, not a stage (questions 4 and 9a)? Decided (see Decided, question 7).
   - **A second board by labels** (the author, 2026-11-08), a point for discussion, not a decision:
     e.g. planning tasks, the ones that give birth to promises, kept off the working board — not
     by a second board right away but by labels: a board does not show tasks with certain labels,
     another board shows them. Goes with labels (later) and boards' filters.
8. ~~**How long a task lives.**~~ Answered with question 1: tasks and Topics are kept (see
   Decided).
9. ~~**The external tracker later.**~~ Decided (see Decided). Nothing, an import, or keeping both in step through the Team's
   own Assistant (the server still holds no credentials)?
9a. ~~**Whose move: where the agent's work ends and the human's begins**~~ Decided (see Decided);
    the discussion kept below. (Raised by the author,
    2026-11-08). An Assistant finishes the analysis, marks the stage done and asks its human
    "continue?"; the question hangs unanswered. That time is nobody's: the agent does not work and
    the human has not read the question yet. With 3–5 tasks run in parallel (the human works out
    forks with an Assistant in one task while another Assistant writes code in another),
    parallelism starts to cost, and only a detailed log shows how much. It first looked like a gap
    between two stages; in fact it is a delay between the executor (the Assistant) and the one who
    makes the final decisions (the human). The log has to catch it.
    - Proposed (2026-11-08, Claude): whose move is a dimension of the task's timeline over the
      status, with four values: the Assistant, its own human, another person, something external.
      The plugin's `Stop` and `UserPromptSubmit` hooks, which Claude Code runs on its own, record
      the moves between an Assistant and its human; Coloqo sees a move to another person by an
      addressed Message and the answer to it; external waits are marked explicitly. Intervals are
      kept, not single prompts. Accepted 2026-11-08.
    - **The purpose (2026-11-08, the author):** real figures, facts to work on the Team's
      efficiency with; never watching or control in the bad sense. Telling "not read yet" from
      "reading and thinking" is not needed: the human's share of the time grows with the number
      of parallel sessions, and at some number a person's efficiency drops because of the sessions
      themselves; the figures show it. The aim is that a person can check themselves and see their
      real figures. When the lead computed the coefficients and showed them to the Team, it turned
      out each person's intuition differed and did not match reality: a colleague thought very slow
      was slow only on some tasks; the lead's own high speed came largely from overtime, which made
      the rest of the Team look slow to him. Useful to everyone, the lead included.
10. **Promises in detail, and names** (narrowed 2026-11-08, after promises became a task type).
    The workflow and fields of a promise: decided (see Decided, question 10, part 1); promises
    across Areas: decided (part 2); the names: decided (part 3). Question 10 is settled.
    The built-in product workflow of a promise (e.g. planned → in progress → delivered / not
    delivered / cancelled) and a promise's fields (a period, the list of deliveries). The name of
    a promise of promises (candidates: Goal, Initiative, Objective; not "direction", which is what
    Areas are). The name of the permanent section for Topics without a task (candidates: Hallway,
    Lounge, Commons, Free Topics), and with it the letter of free Topics (Hallway gives `H-5`;
    question 5, part 2). Whether an upper promise may hold promises of several Areas.

### The coefficients

**Deferred to the next feature (2026-11-08, the author):** estimates and coefficients are a feature
of their own, which a Team may not want (they spend tokens); the tracker comes first. What the
tracker must collect for them from day one is decided (see Decided, "What the tracker collects for
the measurement").

11. **Who estimates, and where it runs.** The estimator is a model call with a fixed instruction.
    Does it run in the Assistant's session (the Team's model and key, as now), in a Worker
    (decision 0015), or on the server (our model costs, the task text goes to us)?
    - Proposed (2026-11-08, Claude), not decided: not the session (it knows the task's history,
      so it is not blind, and each person's model differs) and not the server (our costs, task
      text sent to a model provider on our behalf, a model key on the server). The plugin runs a
      separate `claude -p` call with a clean context, on the instruction and model the Team set,
      stored in Coloqo with versions; the server prepares the blind batch (scrubbed, anchors mixed
      in); the plugin posts the results. A Worker estimator later. The early estimate at a task's
      creation, the full one at entering the code stage; the anchors re-estimated monthly. Turning
      estimates on is a Team's flag; off, it costs no tokens.
12. **What counts as the fact:** the throughput window, activity days, or explicit marks in the
    Topic (§1.3)? The window needs no new habits; explicit marks are precise but cost discipline.
13. **Who sees k.** A person's speed is personal data and sensitive inside a team (decision 0014).
    Only the person and the lead? The whole Team? Is it kept, or computed on demand and not stored?
    The same for whose-move figures (question 9a). Decided inside the principle at the top of this
    file: figures are a mirror for the person and material for the Team's conversation, not an
    instrument of oversight.
14. **Evenings and weekends:** count them as working time, as overtime, or leave them out?
15. **Onboarding and learning:** a task with an estimate, or excluded from the measurement?
16. **Raw or prepared:** by a rule on the early text, by the gap between the two estimates, or by
    the assignee's mark?

## Decided

- **Question 1 (2026-11-08, the author).** Coloqo is the system of record for a Team's working
  tasks; the external tracker stays the system of record for what the Team keeps there (large
  tasks that move about once a week). A link to an external issue is its key and URL, with no
  sync and no Team credentials on the server: W4's reasons against a server integration stand, and
  an Assistant moves the external issue with its own tools when the Team rules ask. A task has any
  number of links, and an external issue may be linked from several tasks; duplicating and
  breaking down are the same link. The tracker is the Team's choice: a Team without it keeps
  working as now, a Topic with the key of its own tracker's issue. Of W4 this reverses only "why
  not our own task board"; the Workers' queue by a tracker filter is left for later.
- **Topics are no longer deleted (2026-11-08, the author).** A task is a record kept until deleted,
  and the Topics of a task are kept with it; with tasks and their Topics kept anyway, deleting the
  other Topics no longer saves enough to be worth it — the disk was the reason for it. This
  reverses the "archived for N days → deleted down to the card" part of decision 0021 for every
  Topic; closing, the archive list and reopening by a new Message stay. It also removes the
  measurement's "retention ate the history" problem (§2). Question 8 is answered by it.
- **Question 2, task and Topic (2026-11-08, the author).**
  - **A task is an entity of its own; a Topic refers to it** by a nullable task id. The model lets
    a task have many Topics, but the first version allows one, by a unique index: Assistants lean
    to bureaucracy and would open Topics by classifications of their own, dozens a day per task,
    while one long feed is easier to live with than many short ones. Lifting the limit later is
    dropping the index, with no data to migrate; a "main Topic" mark comes only then. A side
    question to a colleague goes into the task's Topic, addressed to that person (decision 0029).
  - **The timeline lives on the task**: status changes, stages, later waits are the task's events,
    and the Topic's feed shows them as service lines, as it shows stages now. It does not depend on
    the conversation.
  - **A Team without the tracker has tasks too.** A Topic opened for a task gets a task, created by
    `open_topic` itself, so the Assistant's tools do not change; its status moves by a built-in,
    hidden minimal workflow (its composition is question 4: "to do → in progress → done" is not
    enough for the measurement); the workflow editor and the boards are off. Turning the tracker
    on is a switch, not a migration: the tasks and their statuses are already there.
  - **Topics without a task exist** and live in a permanent section of their Area (its name is
    question 10). The author first saw every Topic as belonging to a task, since questions come up
    during work; but making a task for every question brings the bureaucracy back. What is not
    anyone's work item gets its own place, like the off-topic corner of old forums. In the data it
    is no group row: Topics with no task, which the web shows as the section.
  - **Groups.** Inside an Area a Team groups tasks, with their Topics, by its own logic: the
    prototype team groups them by promises, the large commitments of a month that tasks work
    towards; another Team may group by releases or clients. Coloqo knows a group, not a promise: a
    title, a description, external links (e.g. to the large issue in the external tracker that
    moves weekly). A task belongs to one group at most, or to none (hot work outside any promise).
    A month plan (§1.5) is in effect a set of promises, so plan against fact can be read per group.
    The rest of groups is question 10. **Revised the same day: a promise is a task of its own type,
    not a separate entity** (see "Promises and the hierarchy" below).
- **Question 3, the scope of a workflow (2026-11-08, the author).** "Defined in the project" means
  the Team: a project in Coloqo is a repository linked to a Team (decision 0020), not a scope of
  tasks.
  - **In the data** a workflow is a row of the Team, and an Area points to one; a task finds its
    workflow through its Area. Several Areas may share a workflow, as projects share a workflow
    scheme in the external tracker.
  - **The first version** shows it as one workflow per Team: every Area points to it, and there is
    one editor; the web offers no "a workflow of its own for this Area".
  - **Later**, a workflow of an Area's own is a second row and a changed pointer, with no tasks to
    migrate; a scope by task type (one workflow for bugs, another for features) may come after.
  - **Left for then:** moving a task between Areas with different workflows needs a mapping of
    statuses; with one workflow it cannot happen.
- **Question 4, the minimal workflow (2026-11-08, the author).** Terms corrected with question 6:
  what moves is a task's **stage**; a **status** is a Team's grouping of stages, shown as a column
  of the board (question 7).
  - **A stage has a kind.** Coloqo knows a fixed set of kinds; the measurement, the boards and the
    reports read the kind, never the name. A Team names its stages as it likes and may add its
    own, each of one kind, so renaming "Review" or splitting it in two does not break the figures.
  - **The kinds**, by category:

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
    | finished | done | verified in prod; the end of the window |
    | finished | cancelled | closed without a result; not counted as work done, the time spent stays visible |

    "Before code" is analysis to agreement; "code → prod" is code to delivery.
  - **The built-in workflow** has one stage per kind, in this order: Backlog → Analysis → Design →
    Documentation → Agreement → Code → Review → Delivery → Done, and Cancelled. A Team without the
    tracker moves by it too (question 2).
  - **Moves are free within work**, back ones included (review → code): the measurement counts time
    by kind. The finished stages are final (question 6). A graph of allowed moves comes later, as
    rows.
  - **A wait is not a stage** but a mark over any stage (question 9a): a "Blocked" stage would
    erase where the task stood.
  - **A stage may be passed at once with a mark**, for any stage: the timeline keeps "skipped:
    no documentation changes", "skipped: no agreement needed". For the measurement "there was no
    such stage" differs from "the stage took 0 minutes".
  - **The Team's owner edits the workflow in the web.** Renaming and reordering are free. Removing
    a stage that has tasks asks where to move them; the history keeps the old name and kind.
  - **Only backlog and done are required**: a Team may remove the stages of every other kind (a
    Team without docs in git has no documentation stage, one without agreement removes it).

- **Question 5, part 1: the assignee and the author of events (2026-11-08, the author).**
  - **The assignee is a human.** Responsibility is always a human's, whatever the name; an
    Assistant and a Worker are the human's tools, not assignees. A task a Worker does is assigned
    to the human who runs it (its responsible human, decision 0015). Decision 0015 calls a Worker a
    Team Member and lets it hold a Topic: holding stays possible (the holder acts, the assignee
    answers for it), but a Worker is never a task's assignee. To be reconciled with 0015 when
    Workers are designed; 0015 is not changed now.
  - **Every event has an author:** an Assistant (a session), a Worker or a human in the web, and the
    human behind it. So the analysis can tell what a person's sessions did from what their Worker
    did; otherwise a Worker's output would silently inflate its human's speed.
  - **An assignee may be set in any status, the backlog included**: assigning is part of planning.
    Any human of the Team, or an Assistant on their behalf, may assign; permissions (e.g. only the
    lead) come later.
  - **A person's time on a task starts with its first move into work** (from the to-do category to
    in progress), not with the assignment: the assignment is the plan, the move is the fact.
  - **A task with no assignee is assigned by its first move into work** to the human on whose
    behalf the move is made: from that moment their time is spent on it.
  - **A task assigned to another human is taken only by an explicit reassignment**, an event of its
    own; an Assistant cannot silently take a task planned for someone else.
  - **Later moves do not change the assignee**: the lead moving a task out of agreement or a
    reviewer out of review are events with their authors.
  - **Creating a task is work too, and an event**, with its author and its source: the task within
    which it was created, usually the task whose Topic the creating session holds. The time spent
    creating it belongs to the source. A task with a source was found during the work; one created
    without a source (in planning) was planned — the "plan against fact" of §4 reads it. With no
    held task the source is empty (later, perhaps, the plan).
  - **No co-assignees**: a colleague's help is visible as another person's move (question 9a).
  - **Assignee history** splits a task's time when it is reassigned midway; this closes the limit
    "the tracker's assignee is the current one" of §1.7.

- **Question 5, part 2: a task's name, title, description and outcome (2026-11-08, the author).**
  - **The data and the presentation are separate.** In the data a task and a Topic are different
    entities (question 2); in the web, while a task has one Topic, they are one thing with one
    name.
  - **The letter `T` goes to tasks:** `T-42`, at `/team/acme/task/42`, a Message in it
    `/team/acme/task/42#m-5`, another Team's `globex/T-42`. Numbered per Team from 1 without gaps,
    as Topics are now (decision 0025); moving a task between Areas does not change its number. A
    single letter is also never taken for an external tracker's key, which has at least two
    letters (from memory, unchecked).
  - **A task's Topic has no number of its own**; it is reached through the task. With several
    Topics later, `/team/acme/task/42/topic/N`, numbered within the task; the address without the
    suffix opens the first.
  - **Free Topics get a letter and a counter of their own** in the Team, chosen with the name of
    their section (question 10), so a free Topic is seen as free at once. A free Topic that grows
    into a task becomes the new task's Topic, and its former name keeps leading there, as former
    slugs do (decision 0025).
  - **Addresses (2026-11-08, the author, after a review note on the old links):** a free Topic is
    `F-5` at `/team/acme/topic/5`; a task's Topic opens at `/team/acme/task/47` and
    `/team/acme/task/47/topic`. Existing Topics are, at the migration, free Topics that became tasks
    with the same numbers: those numbers stay taken in the free series, and both counters continue
    after them, so `/team/acme/topic/12` in old MRs and the API calls of old plugins lead to task 12
    by the one rule "a free Topic that became a task leads to it". `/team/acme/free/5` was weighed
    and dropped. Written into decision 0031.
  - **The plugin's tools take both forms**: `T-42` reads a task's Topic, the free letter a free
    Topic.
  - **Existing Topics become tasks with their numbers**: tasks of a Team without the tracker, with
    a status by the built-in workflow (an open Topic in progress, a closed one done); the Team's
    task counter continues its Topic counter, so every `T-12` already in an MR or an issue keeps
    its meaning. Most pilot Topics are task Topics anyway (decision 0023); the few questions among
    them become tasks of the past. Splitting them by signs (an issue key, stage notes) was weighed
    and dropped: it needs a table of former numbers and a rule that would err.
  - **A Team key (`ACME-42`) is a possible setting for later**, a second name of the same task; the
    short form always works. Weighed after reading how other trackers do it: the URL already names
    the Team, so the key is cosmetic. Jira, Linear and ClickUp key tasks by a project, a team or a
    space and renumber a task moved out of it, keeping the old keys as redirects; a key on the
    Team, which tasks do not leave, never renumbers.
  - **The title, the description (Markdown) and the outcome live on the task**; the Topic shows
    them, and the task's timeline in the same feed, as GitHub's and Linear's issues mix comments
    and events in one feed. A free Topic keeps its own title and outcome. A task Topic's external
    issue key comes from the task's links (question 1).
  - Noted from other trackers, not decided: the outcome kept apart from the status (Jira's
    resolution; GitHub's close reasons `completed`, `not_planned`, `duplicate` with the issue it
    duplicates) — a "duplicate of T-12" link may later refine "cancelled".

- **Promises and the hierarchy; question 5, part 3: subtasks (2026-11-08, the author).** Revises
  the "Groups" point of question 2.
  - **The author's practice.** Two attitudes to tasks were met: the product one, where a story is
    a user story and tasks implement it (handy for product owners and the business, awkward for
    developers), and the technical one, where a story is a technical piece and its subtasks are
    the parts of its implementation. Coloqo needs something between. In the external tracker the
    author kept epics that hold epics, and forbade stories in an epic that holds epics, so that it
    did not turn into hell; in practice the child epics of the first level always held stories,
    and when one started to grow sub-epics, its stories were moved into them.
  - **The levels.** Promises and what is above them are product deliveries: the business looks
    that high and wants to see clearly what it is given or loses in product terms. The technical
    level starts at the task (the external tracker's story): first it describes its delivery in
    product terms, the rest — details, how it is done — is technical. A task may have no product
    delivery of its own, being purely technical, and still work within a promise worded in product
    terms ("improve the search results", "speed up the home page"). A subtask is always technical.
    This matches the common shape of the known methods (Jira's initiative → epic → story →
    sub-task, SAFe, OKR): product above, technical below, the story as the seam.
  - **A promise is a task of the type "promise"**, in the hierarchy by `parent_id`; not a separate
    entity. So a promise has a Topic (the discussion of how to keep it before its tasks exist),
    an outcome, external links (the large issue in the external tracker) and a timeline, as any
    task, and its number is `T-40` too; the web tells the type by an icon. Planning (Later) works
    with the same entities.
  - **A promise holds either promises or tasks, never both.** A promise of promises is not a type
    of its own but a promise that holds promises; the web calls it by a word of its own (its name
    is question 10). When a promise gets its first sub-promise, its tasks have to be moved into
    sub-promises first, or the server refuses. The depth is not limited in the model; two levels
    are expected in practice.
  - **A task holds only subtasks; a subtask holds nothing.** A subtask is a full task with a parent
    task: its own status, assignee, timeline and Topic, so time attaches to it without guessing
    (§3 item 3). A parent's status is not derived from its subtasks (as in Jira); "all subtasks
    done → the parent done" may come later. Against bureaucracy, a rule for Assistants, not the
    model: a subtask only when a part goes to another person, ships as its own MR or release, or a
    human asked for it — to be set with the Team rules.
  - **A task may stay outside promises** (hot work from the reserve).
  - **Workflows by type.** A promise has a built-in product workflow of its own (its composition is
    question 10); tasks and subtasks share the workflow of question 4. This brings forward a part
    of question 3's "a scope by task type": two types from the first version. The measurement reads
    only tasks and subtasks: a promise's statuses are the product level, not work.
  - **Groupings without an end** (a client, a component) are labels, later.
  - Left for later: a task's product delivery as an optional one-line field apart from the
    description, so the business reads a promise's deliveries without the technical text, or as a
    convention in the Team rules (question 5, the other fields).

- **Question 5, part 4: estimates and the other fields (2026-11-08, the author).**
  - **An estimate is an entry of the task's timeline**, not a single field: hours, a breakdown as
    text ("the canon — 3 h, service A — 4 h"), its kind (early or full), the estimator's version
    (instruction text and model), its author and date. The task shows the latest estimate of each
    kind; the history stays. Re-estimating the anchors for the drift (§1.5) writes the same
    entries. Who estimates and where (a session, a Worker, the server) is question 11; the storage
    does not depend on it.
  - **Order**: a manual order within a status, by dragging on the board; it stands for priority —
    what is higher matters more.
  - **No priority field** in the first version: order gives the same without a second dimension
    that drifts apart from it.
  - **No due date on tasks**; promises have a period (question 10).
  - **No assignee's own estimate** in the first version: the common yardstick is the model's
    estimate (§1.1).
  - **Labels** come later, with the groupings without an end.
  - **The product delivery line** stays left for later: a field, or a convention in the Team rules.
  - The fields of the first version, then: type, title, description, status, assignee, Area,
    parent, external links, outcome, order, and estimates as timeline entries.

- **Question 6, who moves a task, and stages against statuses (2026-11-08, the author).**
  - **Stages and statuses.** The detailed steps (analysis, design, documentation, …) are a task's
    stages; there are too many of them to see on a board. A status is a Team's grouping of stages,
    shown as a column: e.g. "To do" (backlog), "In progress" (analysis to delivery), "Done" (done,
    cancelled). The Assistant moves the stage; the status follows from it by the Team's grouping.
    How a Team groups stages into statuses is question 7.
  - **A stage note in a task's Topic is a change of stage**: the event keeps the stage's kind and,
    if wanted, a line of comment. The free-text stages of `note_stage`, which the measurement had
    to interpret (§2), are not needed for tasks. Progress notes stay as they are: a story, not a
    stage.
  - **Only an Assistant moves a task.** Moving it is work, and the Assistant does more than move
    it: the notes, the skipped-stage marks, the outcome. A human in the web neither moves stages
    nor closes tasks; they ask their Assistant (the lead agreeing a decision too). Of the
    Assistants, only those of the assignee move it; another Assistant writes in the Topic, as with
    closing now (decision 0021). A human may still close a free Topic in the web.
  - **A human in the web plans**: changes the order within a status (dragging up and down; the
    order stands for priority, question 5) and sets the assignee. Neither is work, and neither
    needs notes beyond the fact.
  - **The Assistant's actions:**

    | When | Action | What happens |
    |---|---|---|
    | work found along the way | create a task | backlog; the source is the current task |
    | a human asks to take a task | take the task | to analysis, assigned (if no assignee), its Topic opened and held, in one action |
    | new work with no task (a Team without the tracker) | open a Topic for a task | the task is created at once in analysis, as `open_topic` does now |
    | the next step | change the stage | possibly with "skipped: reason" |
    | done or cancelled | close the task | stage done or cancelled, with an outcome |

  - **Closing a task closes its Topic**; the outcome is required, as in decision 0021.
  - **A finished task is not reopened**: done and cancelled are final. A fix is a new task. No
    relations between tasks ("blocks", "duplicates", "fixes"): a mention is enough — the new task's
    description names `T-42`, and the web makes it a link; when the new task was created within the
    old one, that is already its source (question 5). A Message in a finished task's Topic (a
    question about it) may be written and changes nothing in the task.
  - **Closing for inactivity (30 days, decision 0021) does not apply to tasks**: closing a task by
    itself would write a false outcome. A task in work with no activity gets only a notice to its
    assignee. Free Topics keep the rule.
  - **A Team without the tracker** moves stages by the same actions: the board is hidden, the
    Assistant sees the built-in workflow. Its timeline and measurement exist.
  - **Whose move** is written automatically (question 9a), apart from these actions.

- **Question 7, boards (2026-11-08, the author).**
  - **In the data a board is an entity of the Team**: ordered columns, each a set of stages; every
    stage is in exactly one column of a board. A task's status is the column of the Team's main
    board its stage is in. A second board later (e.g. the lead's, with agreement as a column of its
    own) is more rows; tasks are not touched.
  - **The first version shows one board per Team**, with built-in columns: "To do" (backlog), "In
    progress" (analysis to delivery), "Done" (done, cancelled). The Team's owner edits the columns
    in the web, e.g. splits "In progress" to show "Agreement" and "Review" apart.
  - **A card shows** the number, the title, the assignee, the stage (as a mark within the column),
    the promise and whose move it is (question 9a), so the tasks waiting for a human are seen at
    once.
  - **Tasks and subtasks are on the board**: a subtask has its own assignee and must show in a
    filter by person; its card shows the parent's number.
  - **Promises are not on the board**: they have a view of their own, a tree of promises with their
    tasks and progress; the product level is not mixed with the working board.
  - **Filters** by Area, assignee and promise are parameters of the view, not stored boards; a link
    keeps them.
  - **"Done" shows the tasks finished in the last two weeks**; the rest are in the list and search.
  - **A Team without the tracker** has the board hidden (question 2).
  - **A "Waiting" column** (the prototype team has one; examples: a token from the company's
    process after the Team's side of an integration is done, an external system's specification
    before its code). A wait stays a mark over a stage; the column is a view.
    - **A column is a set of stages or a condition**, "has an active wait". A task with an active
      wait stands in such a column instead of its stage's column, whatever its stage; when the wait
      ends it returns.
    - **The card shows the stage and what is awaited**: "Code · waiting: a token from the
      infrastructure", "Design · waiting: the specification from team X".
    - **The Assistant sets the mark explicitly**, "waiting: whom or what" and "resumed" (§3 item 2).
    - **The measurement loses nothing**: the stage's time runs on, and the wait's interval with its
      reason is kept apart, so the Team can see how much outside dependencies cost it, and which.
    - **Only explicit external waits go to the column.** A wait inside the Team (a question to the
      lead, an agreement) shows on the card as "move: alice" (question 9a); otherwise half the
      tasks would land there at every question.
    - **The built-in board has no such column**; the owner adds it in the web like any other.

- **Question 9, the external tracker later (2026-11-08, the author).** The bridge is the
  Assistant, not the server, and not only in the first version.
  - **The Assistant keeps Coloqo and the external tracker in step**, with its own tools for the
    tracker (an MCP server, a CLI) and its human's rights there. The Team rules say what to update
    and when, e.g. "when a task linked to an epic closes, comment its outcome in the epic".
  - **An import** ("move epic ACME-42 with its subtasks into a promise") is the Assistant's work
    too: it reads the external tracker and creates the promise and tasks with links. The server
    needs nothing for it.
  - **No server integration on the cloud instance, now or later**: W4's reasons stand (the Team's
    credentials, a corporate tracker unreachable from the cloud, the Team's data with us).
  - **On a self-hosted instance** a server integration may come one day: the tracker is in the same
    network and the operator is the company itself. A paid feature on top (M1), not now.
  - It costs no code in the first version and has no sync to break on diverging workflows; the
    price is that the external tracker changes only when an Assistant changes it, enough for large
    tasks that move about once a week.

- **Question 10, part 1: a promise's workflow and fields (2026-11-08, the author).**
  - **The built-in stages of a promise:**

    | Category | Stage | Meaning |
    |---|---|---|
    | to do | Draft | worded, being discussed and estimated, not given yet |
    | in progress | Given | given for a period; tasks work towards it |
    | finished | Delivered | delivered |
    | finished | Not delivered | the period ended without the delivery |
    | finished | Withdrawn | removed on purpose, e.g. priorities changed |

  - **No "in progress" stage of its own**: "Given" covers it, and the work shows in the tasks.
  - **"Not delivered" and "Withdrawn" are different outcomes**: a miss against the period and a
    decision; for the Team's conversation they differ. A partial delivery is told in the outcome's
    text.
  - **A finished promise is final**, as a task is. An undelivered promise is not extended: a new
    promise is given for the next period and the unfinished tasks move into it, so plan against
    fact honestly shows that what was promised for October did not fit into October.
  - **An Assistant moves the stages** at its human's request, as with tasks (question 6); giving or
    withdrawing a promise is a human's decision.
  - **A Team may edit the promise workflow** by the rules of the task workflow (question 4).
  - **The fields**, besides those every task has (title, description, assignee, links, outcome): a
    **period**, a start and an end date, usually a month. The **assignee** is the human answering
    for the promise, usually the lead.
  - **Computed, not stored:** the sum of its tasks' estimates; progress by the number of tasks and
    by estimated hours, done against all; the list of deliveries, once a task's delivery becomes a
    field.
  - **A promise of promises** has the same stages and fields; its progress is counted over the
    promises it holds.

- **Question 10, part 2: promises across Areas (2026-11-08, the author).**
  - **A task lives in its Area**: every task has exactly one Area (question 5). It is listed in
    that Area with its Topic, as a Topic is listed in its Area now; it finds its workflow through
    the Area (question 3); the board filters by it (question 7). The Area can be changed; the
    number stays (question 5, part 2). A promise, being a task, has one Area too.
  - **What a promise holds may live in any Area of the same Team**: "billing by December" in
    Development may hold the API task in Development, the payments report in Analytics and the
    payment screen in Design. For the business it is one delivery; requiring one Area would split a
    cross-functional promise by direction.
  - **The board filtered by a promise** and the promise tree show all its content, from whatever
    Area. Workflows do not clash: promises and tasks are different types, and a task takes its
    workflow from its own Area.
  - **Never across Teams**: a promise and all it holds belong to one Team.

- **Question 10, part 3: names (2026-11-08, the author).** They join the product vocabulary next
  to Team, Area and Topic.
  - **Promise** (Russian «Обещание») is the name of the type. Product language that carries the
    sense of a commitment, and not confused with the external tracker's epics a promise links to.
    Epic and Commitment were weighed.
  - **Goal** (Russian «Цель») is what the web calls a promise that holds promises; not a type of
    its own (question 5, part 3). Initiative and Objective were weighed.
  - **Free Topics** (Russian «Вольные темы») is the permanent section of an Area for Topics without
    a task; a free Topic's letter is **`F`**: `F-5`, another Team's `globex/F-5`, numbered per Team.
    Hallway, Lounge and Commons were weighed.

- **What the tracker collects for the measurement (2026-11-08, the author).** Estimates and
  coefficients go to the next feature; the principle: **data that cannot be rebuilt afterwards is
  collected by the tracker from day one; the features that read it may come later.**
  - **A task's description has a history**: editing it is a timeline event with the new text. The
    method estimates a task by its early text, as first written, and by its full one (§1.2); with
    only the current description, the early text is gone at the first edit, and every task created
    before estimates arrive would lack its early estimate. It also shows how a task changed while
    worked out.
  - **Whose move is recorded from day one** (question 9a), even before any measurement: a person
    sees their own intervals (the mirror); when the measurement comes, the Team already has months
    of history. Recording only once a Team turns the measurement on was weighed (less data about
    people, decision 0014) and dropped: the first figures would come a month after turning it on.
    Who else sees them is question 13.
  - **Already in place:** the timeline is one table of events, a kind and its data, so estimates,
    waits, skipped stages and move intervals fit without migrations; stage times, assignee history
    and keeping everything are decided. Times are kept in UTC; a person's time zone, needed for
    evenings and weekends (question 14), can be added later.

- **Question 9a, whose move (2026-11-08, the author).** Whose move is a dimension of the task's
  timeline over the status, with four values: the Assistant, its own human, another person,
  something external.
  - The moves between an Assistant and its human are written by the plugin's `Stop` (the Assistant
    ended its turn: the move is the human's) and `UserPromptSubmit` (the human answered: the move
    is the Assistant's) hooks. Claude Code runs them on its own, so they do not depend on the
    Assistant's discipline or judgement. They work where the plugin is installed, the project is
    linked and the session holds a task's Topic.
  - A move to another person Coloqo sees by a Message addressed to them and the answer to it.
  - External waits (CI, an account, a colleague's release) are marked by the Assistant
    explicitly, as are statuses and skipped stages: only it knows their meaning.
  - Intervals are kept ("the Assistant's move 10:02–10:17"), not every prompt.
  - "Not read yet" and "reading and thinking" are not told apart, and need not be: the human's
    share grows with the number of parallel sessions, and the figures show where a person's
    efficiency starts to drop because of it. When a person's move in task A coincides with their
    prompts in the session of task B, the wait is the cost of parallelism.
  - **The purpose:** figures are a mirror for the person themselves and material for the Team's
    conversation, not an instrument of oversight (the principle at the top of this file).

## Later, after the tracker is built

- **Update the vocabulary** when the tracker's decisions are written down: Task, Promise, Goal,
  stage, status, board, Free Topics join Team, Area, Topic in `docs/product/vision.md` §4 and in the
  project's `CLAUDE.md`; "a Topic is one question in an Area" changes for task Topics.
- **Carry the principle "figures are a mirror" into the documentation** (the author, 2026-11-08,
  "in several places"): the decision record of the tracker and of the measurement, `README.md` and
  `README.ru.md` once figures are a feature, and the web page that shows figures. Already in this
  file and in the product statement (M1, refined 2026-11-08).

- **The cloud instance's database.** Keeping every Topic and task makes the data grow without a
  ceiling. Work out moving the cloud instance to the hosting provider's managed PostgreSQL instead
  of PostgreSQL on the VDS (decision 0016): cost, backups, the migration, what stays on the VDS.
  The author asked to take it up once the tracker is implemented (2026-11-08).
- **Planning** (the author, 2026-11-08). With promises and groups in Coloqo, the promises
  themselves are given in Coloqo: a plan, then following how it is kept. Groups grow out of the
  plan, and the month plan of §1.5 (capacity, the 70 % fill, plan against fact) fits in with it.
  To be worked out later, on top of the tracker.
- **A shared Topic for agreeing releases** (the author, 2026-11-08). When a colleague releases the
  services a task touches, a common "release agreement" Topic has long been missing; with the
  tracker it is clear where it lives, and it should be created automatically — perhaps daily,
  once some task has reached the MR. To think over; it meets `2026-10-21-team-announcements.md`
  (the Releases Area, "who is releasing now"). To weigh against the product statement, question 4
  (2026-10-20): a permanent "Release coordination" Topic was already replaced there by a Releases
  Area with a Topic per release (a release is a task), because a Topic with no end is a channel
  under another name; a daily Topic created automatically sits between the two.

## Facts checked (2026-11-08)

- The measurement's data and scripts live in the prototype team's workspace; the Coloqo timeline
  there is text written by the model while reading Topics, with no calls to Coloqo.
- Decision 0021: Messages of a closed Topic are deleted after N days, 7 on the cloud instance; the
  card (number, title, Area, tracker key, outcome, holder, dates) remains. Stage notes are Messages
  and go with them.
- `note_stage(topic, text)` takes free text only; there is no stage kind and no wait mark.
- Vision W4 (2026-10-17) rules out a task board of Coloqo's own; decision 0015 keeps the server out
  of the tracker.
