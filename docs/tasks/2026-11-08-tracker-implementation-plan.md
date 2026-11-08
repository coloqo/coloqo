# The task tracker: implementation plan

**Status:** a plan for discussion (2026-11-08). The design is decisions 0030–0033; the discussion
is `2026-11-08-speed-coefficients-and-a-task-tracker.md`.

## Principles of the order

- **Each slice is a PR and a release that leaves everything working**, members on the old plugin
  included: the server goes first and speaks to old plugins by their `X-Coloqo-Plugin` version, the
  plugin follows, the web comes with the server (it is bundled in the server's wheel).
- **The data model comes whole in the first slice**, behaviour later. Columns that cost nothing
  (`type`, `parent_id`, the timeline table) go in at once, so later slices add no data migrations
  of existing rows.
- **What cannot be rebuilt is collected from the first release** (decision 0033): the timeline,
  description history, whose move.
- A migration that rewrites data: `backup.sh` before the deploy (the deploy flow). The author (2026-11-08): with one pilot team, its data may be wiped if a migration
  ever needs it; the plan still migrates it, and the backup stays.
- **Two PRs, plus the pins PR** (the author, 2026-11-08). **PR A** is slices 1 and 2: the server
  with the migration, the API and compatibility, the plugin, and the minimum of web for links to
  work; after it Assistants keep tasks and the timeline starts filling. **PR B** is slices 3 and 4:
  the web and promises. One PR is possible (only the pins need a PR of their own, after PyPI, and
  the server must be deployed before plugin 0.7.0 reaches anyone, which is the order of tags, not
  of PRs); two keep the data migration checked in prod apart from the new interface, keep review
  rounds readable, and bring the use earlier. Slice 1 alone gives nothing: the server would know
  tasks and the Assistants would not.

## Slice 1 — the server: model, migration, API, compatibility

Nothing changes for a member yet but the deletion of closed Topics, which stops.

**Data** (one Alembic migration, `0010_tasks`):

| Table | What it holds |
|---|---|
| `workflows` | a Team's workflow: the type it serves (task, promise) |
| `stages` | a workflow's stages: name, kind (enum, decision 0032), position |
| `tasks` | team, number, type, area, parent, title, description, stage, assignee (user), outcome, order key, source task, created by, created/finished times |
| `task_links` | a task's external links: key, URL |
| `task_events` | the timeline (decision 0033): task, kind, time, author user and assistant, data (JSONB); kept forever, unlike the stream's `events` (a week, decision 0008) |
| `topics` | + `task_id` (nullable, unique: one Topic per task); `number` becomes nullable — it is the free series' number (`F-`), and a task's Topic created as such has none |
| `teams` | + `last_task` (the task counter); `last_topic` stays as the free series' counter; + `tracker` (on/off, decision 0031) |

`Area.workflow_id` points to the Team's task workflow (decision 0032). Boards wait for slice 3.

**The migration of existing data** (decision 0031):

- Each Team gets the built-in task and promise workflows.
- Each existing Topic becomes a task with the same number: title, outcome and Area copied, `issue`
  as a link, the Topic's `task_id` set, its `number` kept (taken in the free series). Assignee: the
  holder's user, else the creator. Stage: closed → Done; open → Analysis, the timeline event saying
  the migration set it, and the briefing asks each holder to set the real stage at its next session
  (question 1, the author, 2026-11-08; guessing from the last stage note's text was dropped: a wrong
  guess would enter the timeline as a fact).
- The timeline is seeded with "created" at the Topic's creation and "closed" at its closing; old
  stage notes stay as Messages.
- `last_task = last_topic` per Team; both counters continue from there.

**Behaviour:**

- Resolving a number: `T-N` is task N; `/topic/N` is the free Topic N, and when it became a task,
  that task (decision 0031). The web: `/team/acme/topic/12` redirects to `/team/acme/task/12`.
- **Retention (decision 0030):** deletion by time is switched off; `archive_days` (instance and
  Team) is dropped; idle closing stays for free Topics only.
- **A task in work with no activity** (question 4, the author, 2026-11-08): after 7 days with no
  timeline event and no Message in its Topic, its assignee's sessions get a notice through the watch
  and at session start, and again every day until something happens. The notice asks the
  Assistant to tell its user and ask whether the task waits, has moved on or is done, and to move
  or close it only by the answer, never just to quiet the notice (the author, 2026-11-08, after a
  review note: "change its stage, mark a wait or close it" pushes an obedient Assistant to false
  marks that enter the timeline as facts). Daily, because Assistants get it and cannot just
  ignore it. A task with an active wait gets none. Activity counts over the subtree: a task or a
  given promise is quiet only when its descendants and their Topics are too (the author, round 1
  of PR A's review: "if I move a subtask of a task tied to a promise, I move the task and the
  promise too; the work goes on"). Both the threshold and the repetition are Team
  settings (`teams.task_idle_days`, `teams.task_idle_repeat_days`), shown next to the tracker
  switch; 7 and 1 by default.
- **API** for the plugin and the web: tasks — list, read (the task, its Topic's feed and its
  timeline), create, take, change stage (with skip), wait and resume, close, edit the description,
  links, assign and order (the web only); whose-move intervals posted by the plugin, kept by session in a table of their own
  (decision 0033); free Topics
  keep the `/topic/N` paths.
- **Old plugins** (`X-Coloqo-Plugin` below the new release): `/topic/N` means `T-N`, as it did, and
  `open_topic` opens a task's Topic in a Team without the tracker; free Topics are not shown to
  them. The briefing tells them to update (decision 0027). Risk: once a new free Topic exists, an
  old plugin cannot see it; the window is one session start.
- **A Team without the tracker** (question 3, the author, 2026-11-08): taking a task, changing its
  stage with skips, waits and closing work as with the tracker (decision 0032); planning does not —
  creating a task in the backlog and assigning are refused with "turn the tracker on". A backlog
  with no board is a list nobody sees, growing by itself, and a reason for Assistants to make tasks
  nobody asked for; work found along the way is mentioned in the Topic, as now.
- **Events** for the watch: task created, stage changed, closed, assigned.
- **The briefing** gets the task vocabulary and the actions (decision 0032), for new plugins.
- `protocol/openapi.json` and `web` types regenerated.
- **Remove `api/legacy.py`** (plugins older than 0.5.0; its docstring says the release after 0.6.0
  removes it) and `LEGACY_UPDATE` in the briefing (question 5, the author, 2026-11-08): teaching it
  tasks would be work for versions told to update for several releases. No check of prod first:
  there is one pilot team.

**Web in this slice:** the minimum for the links to work — `/task/N` shows the existing Topic page
with the task's title, number and stage; `/topic/N` redirects or shows a free Topic. And the tracker switch in the
Team's settings, for the owner (moved here from slice 3a): the pilot team turns the tracker on right
after the deploy (question 2, the author, 2026-11-08), so its Assistants fill the backlog before the
board comes. The switch is not set by the migration: that would name the pilot team in public code
(the project's boundaries).

## Slice 2 — the plugin `coloqo` 0.7.0

- **Tools:** `create_task`, `take_task`, `change_stage` (with `skipped`), `wait` / `resumed`,
  `close_task` (outcome), `edit_task` (description, links); `open_topic` opens a free Topic or a
  Topic for a new task; `read_topic` and the renderer take `T-` and `F-`; `note_stage` becomes
  `change_stage` for tasks and stays a progress line for free Topics.
- **Whose move:** the hooks already write the marks — `UserPromptSubmit` (`trail.prompt_arrived`,
  which tells a human's prompt from one made by an event) and `Stop` (`trail.turn_ended`). The
  hooks stay offline; the watch, which runs as long as the session, turns the marks into intervals
  and posts them for the task the session holds. No network in hooks, so the hook timeouts (the
  open Windows problem, `2026-10-21-prompt-hook-times-out-on-windows.md`) do not grow. A prompt made
  by an event is not the human's answer: the move stays the Assistant's.
- **The watch's alive cadence**: 10 s, deferred after decision 0029.
- Release order: the package PR with the pins left old → tag `plugin-v0.7.0` → wait for the PyPI
  simple index → the pins PR.

## Slice 3 — the web: the task, the board, the editors

Can be split in two PRs if large.

- **3a. The task page:** the task and its Topic as one — header with number, type, stage, assignee,
  links, outcome; the description with its history; the timeline's events as service lines in the
  feed. The "Free Topics" section in each Area.
- **Two web nits deferred after decision 0029** (question 6, the author, 2026-11-08): online
  sessions listed before offline ones, by word within each group; `sessions.none` in Settings
  ("Сейчас живых сессий нет." / "No live sessions now.") becomes "Сессий нет." / "No sessions.",
  since offline sessions up to 20 minutes are listed too.
- **3b. The board:** `boards`, `board_columns`, `column_stages` (a column by stages, or by the
  condition "has an active external wait"); the built-in board at the switch; cards (number,
  title, assignee, stage, promise, whose move, what is awaited); filters by Area, assignee, promise
  in the URL; "Done" for two weeks; order by dragging and assigning by a human (decision 0032). The
  workflow editor (rename, reorder, remove with "move tasks to") and the columns editor, for the
  owner.

## Slice 4 — promises, goals, subtasks

- Behaviour on the slice-1 columns: the promise type with its workflow, "promises or tasks, never
  both" refused by the server, subtasks one level under tasks, a promise's period and its human,
  computed progress.
- Plugin tools to create, give and close a promise; `create_task` with a parent.
- The web: the promise tree with progress; "Goal" for a promise of promises; a promise on cards and
  in the board's filter.

## Not in these slices

Estimates and coefficients (the next feature); a person's figures page (with it); several boards,
labels, a Team key, workflows per Area, a graph of moves; Workers.

## Questions before slice 1

All six settled on 2026-11-08 by the author; the answers are written into the slices above.

1. The stage of an open Topic at the migration: Analysis, marked as set by the migration.
2. The pilot team's tracker: on right after the deploy, by the switch that moves into slice 1.
3. A Team without the tracker: no planning (no backlog, no assigning); taking, moving, closing work.
4. The inactivity notice for a task in work: after 7 days, then daily; Team settings.
5. `legacy.py`: removed in slice 1.
6. The two web nits after decision 0029: in PR B.
