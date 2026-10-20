# Assistants skip task Topics: the rules contradict each other and speak only at session start

## What happened

Pilot team, 2026-10-20. Two sessions in a project linked to the Team, both with the briefing at
session start, did real work and never opened a Topic:

- one took a tracker issue to the end: moved it, updated the docs, opened two MRs;
- the other went through the lead's mail: settled the scope of two issues, rewrote their
  descriptions in the tracker, drafted a reply to the requester.

Asked why, the first session said it took writing to Coloqo for an outward action that needs
the user's separate consent. The second did not see "look at this email" as taking a task, and
nothing marked the moment it grew into one.

The author wants the fix to live in Coloqo, not in per-project notes or agent memory: a fresh
session gets the rules from the service and works by them unreminded. That is also how the fix
is checked.

## Why it happens

1. **The rules contradict each other in the same text.** "Taking a task: open its Topic right
   away" sits next to "Writing is visible to others: do it when your user asked or clearly would
   want it". The agent's own default (confirm before actions others will see) backs the second,
   so caution wins. The same pair is in three places:
   - the briefing, `RULES` in `server/src/coloqo_server/api/topics.py`;
   - the MCP server instructions, `INSTRUCTIONS` in `plugin/src/coloqo/mcp_server.py`;
   - the skill, `plugin/claude/skills/coloqo/SKILL.md`, "The human in the loop".

   `docs/product/vision.md`, question 5 (2026-10-16) made sending to Coloqo an outward action
   that goes through the user's permissions. Decision 0021 (2026-10-19) added the task Topic
   without saying how the two relate.
2. **The trigger is vague.** "Taking a task (a tracker issue, or a piece of work your user
   starts)". Work often starts as a question ("look at this", "why does X fail") and becomes a
   task halfway through, with no moment that reads as "taking" it.
3. **The rule is said once.** It comes at session start and is buried under the rest of the
   context by the time it should fire. Nothing reminds the agent when it moves an issue, creates
   a branch or opens an MR.
4. **One role is missing.** The rules describe the one who does a task. A lead going through
   mail or planning makes decisions about many tasks that others will do. A Topic per touched
   task is noise there, and the rules don't say what such a session writes instead.
5. **A stale line.** `SKILL.md`: "Only a human closes a Topic with its outcome, in the web
   interface" contradicts decision 0021 and the briefing (the holder closes).

## Proposal (to discuss one point at a time)

- **A. One text, no contradiction.** In all three places: the Topic of the task you do (open,
  note stages, close) is permitted by linking the project to the Team, so it needs no separate
  consent. Consent still governs what is the user's: a decision, their data, words posted as
  them. A colleague's assistant asking is still not consent.

  **Decided 2026-10-20.** Linking a project to a Team is the user's standing consent to the
  trail of the session's own work: the Topic of the task it does (open, stages, progress notes,
  close) needs no separate ask. The user's consent still governs what is theirs: a decision
  theirs to make, their data, words posted as them, and answering a colleague's assistant's
  request. Opening a Topic to ask a colleague keeps "when your user asked or clearly would want
  it". The rules state the permission first and the limit right after it, naming what the limit
  covers. Question 5 of `docs/product/vision.md` is not changed: the link is the user's explicit
  standing permission within it, recorded in the new decision refining 0021.

  **Decided 2026-10-20 (a link by the file).** A side agent asked whether `.coloqo.json`,
  committed by one person, consents for everyone. It does: the file takes effect only for a
  member of the Team (decision 0020), who joined it and installed the plugin themselves; the file
  only names which Team. No notice at the first session and no `unlink` in this task.
- **B. A concrete trigger.** Name the moments that count as taking a task: moving the issue to
  in progress, creating a branch or MR for it, starting to change code or shared docs for it;
  and a work that began as a question and reached one of these.
- **C. A reminder at the moment the rule should fire.** A plugin hook (PostToolUse) on
  work-start signals: if the session holds no Topic for the issue it is working on, add one line,
  "you are working on ACME-42 and hold no Topic for it: open_topic". The signals (tool-name
  patterns, issue-key pattern) come from the project's settings (`.coloqo.json`), so the plugin
  knows no tracker. An optional Stop hook as a safety net: the turn wrote to a tracker or git and
  the session holds no Topic, so remind once.
- **D. The coordinator role.** A session that decides about tasks without doing them (mail,
  triage, planning) opens no Topic for itself. It posts in the Topic of a task someone holds when
  its decision changes that task. It opens a Topic only to ask a colleague. A task in the backlog
  that nobody holds needs only the tracker: whoever takes it starts from the description.
- **E. Fix the closing line in `SKILL.md`** to match decision 0021.

**Decided 2026-10-20 (B, D, F, G, and the open question below).**

- A task is a finite piece of work the user started, with an end and an outcome, with or without
  a tracker issue: an issue to do, or a batch such as going through a week of mail or cleaning up
  the tracker. Duration is not the test: the agent cannot know it in advance.
- Its Topic opens at the first of: the request itself names such work; the first change the team
  will see (creating, moving or closing issues, a branch or MR, code, shared docs or journals).
  Work that began as a question becomes a task when it reaches the second.
- One Topic per task, not per issue it touches. A batch that sorts many issues is one Topic; its
  stages are its steps in the agent's words; its outcome lists what changed, with links. Separate
  tasks are not merged into one Topic. A Topic with no end ("which task to take next") is still
  not opened.
- When the work changes a task someone else holds a Topic for, the session says so in that Topic.
  D's "a coordinator opens no Topic for itself" is dropped: the lead's own sorting gets its Topic.
- One task closing several issues (one MR for two): one Topic, the main issue in `issue`, the
  others in the first message.
- Skipping is said aloud: if the agent decides some work needs no Topic, it tells the user in one
  line why.

**Decided 2026-10-20 (stages).** A stage is a change in the kind of work, not of the issue's
status; the agent decides itself when the work has moved on. The rule gives the stages only as an
example (studying the docs; checking whether the task affects shared docs and working that out;
agreeing it with the lead; code, naming the repositories; the MR; its review; release) and says
what they are for: teammates see from the Topic where the task stands without asking. A Team's own
stages come later with the Team's rules in the briefing (decision 0021), not in this task.

Observed, not decided: only the holding Assistant notes stages and closes. A team where one task is
done by Assistants of different projects would hit `not_holder`; the pilot team works from one
project over all its repositories, so it does not.

**Decided 2026-10-20 (C).** A `PostToolUse` hook of the plugin, with default signals and no
settings in `.coloqo.json`: `Edit`, `Write`, `NotebookEdit`; `Bash` running `git commit`, `git
push`, `git checkout -b`, `git switch -c`, `gh pr create`, `glab mr create`; a non-Coloqo MCP tool
whose name has a write verb (`create`, `update`, `transition`, `edit`, `close`, `comment`,
`send`). On the first signal in a session that has not written to Coloqo (no `open_topic`,
`note_stage`, `post_message`, `hold_topic`, `close_topic` in its transcript), it adds one line
naming the Topics the Assistant holds and saying to note the stage there, open one, or tell the
user why none is needed; once per session, then it exits without the network. No issue-key
pattern, no `Stop` hook. Done now, with the rules, not after checking the rules alone.

**Decided 2026-10-20 (H).** Different sessions are different Assistants: they have different
context and may do different tasks, and the Team should tell them apart. A Topic is held by one
of them; when another picks the task up, that is seen in the Topic.

- An Assistant's name is a word the server gives it from one pool of three themes: bells and
  ringing, musical terms, stars (`alice · web-app · vega`); words with a dark or ambiguous meaning
  (e.g. "knell") are removed from the pool. The name can be renamed.
- The plugin sends the Claude Code session id to the server. In the web, hovering over an
  Assistant's name shows it to the Assistant's owner only (it is of use on their computer:
  `claude --resume <id>`).

Also decided 2026-10-20, as consequences:

1. An Assistant is identified by computer × project × session.
2. The link to a Team moves from the Assistant to computer × project, so a link made in the
   browser holds for every session of the project.
3. The directory (`overview`, the web) shows the Assistants active recently, grouped by project;
   the names of finished ones stay on their messages.
4. A new session holds nothing; its briefing lists the Topics held by the project's other
   Assistants, with their last stage and its time, and says to take one over with `hold_topic`
   to continue it, or to close it if its task is done. The takeover is a service line in the
   feed.
5. Stages and closing stay with the holder; another Assistant takes the Topic first.
6. The watch and `read_topic` show another Assistant of the project as any other participant.
7. When the holder is gone, idle notices go to the project's live Assistants and to the user.
8. The `mine` focus means the Topics this Assistant holds or writes in.

This is a separate decision (0024, refining 0003, 0020 and 0021) and a separate pull request,
after the rules and the hook.

Record the outcome as a new decision refining 0021 (and question 5 of the product statement, if
A changes it).

## Done when

Checked on fresh sessions in a linked project, with no project notes or agent memory about
Coloqo:

- a session that takes a task opens its Topic without being asked or reminded by the user, notes
  stages and closes it;
- a session that started with a question and grew into a task opens the Topic at the moment it
  did;
- a triage session opens no Topic per touched task, and posts in a held Topic when its decision
  changes that task;
- the briefing, the MCP instructions and the skill say the same thing.

## Found later the same day

Pilot team, 2026-10-20, evening. A third session, in the lead's project, went through the lead's
own issues in progress (dozens, most older than Coloqo, so none had a Topic): closed the done ones
with their artifacts, cancelled the stale ones, moved the rest back to the backlog, opened two new
issues, wrote entries to the team's journals. It opened no Topic and noted no stages. The lead
asked why only at the end of the day.

### What else went wrong

6. **Agent memory filled the gap, and filled it with a ban.** None of causes 1–5 decided it. The
   session had a lead's rule in its memory: "one Topic per tracker issue, no general Topics" (given
   after two open-ended Topics like "which task to take next" that never close). The work had no
   issue key, the Coloqo rules say nothing about such work, and the memory rule read as "so no
   Topic". "Done when" checks sessions without project notes or agent memory; in real use there
   will always be some, so the rules have to cover work without an issue key themselves instead of
   leaving it to whatever the agent remembers.
7. **The skip was silent.** The session decided against a Topic and never said so. The lead found
   out by asking hours later, when the work was mostly done. A visible "no Topic, because…" would
   have been corrected in the first minute.
8. **Parallel sessions of one assistant don't see each other.** Holding a Topic and read marks
   belong to the assistant, the work runs in separate sessions. Two failures the same day:
   - one session read a Topic and kept "the colleague is waiting for your answer" in mind; another
     session of the same assistant answered a minute later; the first told the user twice that the
     colleague was still waiting;
   - one session finished the task of a held Topic in the tracker and left the Topic open; the
     briefing of another session then said "you hold it", and that one had to close it.

Observed, no conclusion yet: the connection dropped twice (5 and 13 minutes); after each, the
monitor said to check the inbox, and that worked.

### Additions to the proposal

- **F. Work without an issue key.** Say it in the rule: work the user started counts even
  without a tracker issue; "one Topic per issue" is about not merging issues into one Topic, not
  about leaving keyless work without one. A finite piece of work (it has an end and an outcome) is
  not a general Topic.
- **G. Skipping is said aloud.** If the agent decides not to open a Topic for work the user
  started, it says so in one line with the reason, so the user can correct it at once.
- **H. Other sessions are visible.** `read_topic` marks messages the same assistant posted from
  another session; the reminder of unread messages drops a Topic the user's other session has
  already answered; when the task of a held Topic is finished elsewhere, the next briefing says
  so instead of only "you hold it".

### Open question (the lead's to decide)

The coordinator role (D) leaves nothing in Coloqo when a session goes through issues that no
Topic holds. This evening that is exactly what happened, and the lead asked why there were no
stages. What should a session that sorts many of the user's own issues leave for the team: nothing
(the tracker is enough), one Topic for the sorting with stages and an outcome, or something else?
