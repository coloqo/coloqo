# Team rules: how they reach every session

## Why now

Three working files of 2026-10-21 end at the same place:

- `2026-10-21-team-announcements.md`: "before a release, check the open Topics in Releases" has to
  reach every session of every member; an Area's description is read only when an Assistant looks
  at Areas, and an announcement is forgotten by the next session.
- `2026-10-21-assistants-ask-the-human-less.md`: a lesson is a proposed change to the Team rules.
- Vision question 4: releases work only with Area rules.

## Decided before (vision question 11, 2026-10-16)

- Stored in Coloqo, with versions: the Team's set and the Areas' sets that refine it; Markdown.
  Export and import for teams that keep rules in git; the prototype team uploads its rules hub.
- They reach the agent by the plugin's hook at session start: Team rules and skills are placed into
  a local project folder and connected by import in `CLAUDE.md`. The reason given: what is
  connected by import lives for the whole session and survives context compaction, what is read
  once gets lost (the prototype's experience). Area rules come with the Topic: reading a Topic,
  the Assistant gets the current version of its Area's rules.
- Changed by a Topic: anyone proposes, an Assistant included; only a human, the owner of the Team
  or the Area, approves. The Outcome is a new version with a diff; the previous one stays in
  history; Assistants get the new version at the next session start.

Not built: nothing of it exists yet (decision 0017 left Area rules out of the first version).

## Facts checked (2026-10-21)

- **The session start hook runs again after compaction.** The plugin's `SessionStart` hook has no
  matcher, so Claude Code runs it on startup, resume, `/clear` and compaction; this session got
  Coloqo's briefing again after its context was compacted ("SessionStart:compact hook success").
  The briefing ("How to work in Coloqo") already reaches every session this way and comes back
  after compaction.
- **The briefing is plain text the hook prints**; nothing is written into the project.
- **A hook's text is capped at 10,000 characters** (each string on its own, several hooks each up
  to the cap); past it Claude Code saves the text to a file and shows the path and a preview of
  2,000 characters, without asking Claude to read the file. The cap cannot be raised
  (code.claude.com/docs/en/hooks.md). The prototype team's rules are ~48 KB.
- **Claude Code has a rules directory.** Every `.md` under `.claude/rules/` of the project (and
  `~/.claude/rules/` for every project of the user) is loaded at launch, with no import line, at
  the priority of `.claude/CLAUDE.md`; a rule with `paths:` globs in its frontmatter loads only
  when a matching file is read or edited. After compaction the project's `CLAUDE.md` and unscoped
  rules are re-injected from disk. No size limit is documented (code.claude.com/docs/en/memory.md,
  context-window.md). Checked here: a file in `.claude/rules/coloqo/` excluded from git by
  `.git/info/exclude` is loaded; a `claude -p` session with file tools disabled named a word
  written only in it, and answered "none" without the file. Unchecked: whether an edit of a rule
  file during a session is picked up before compaction.
- **No weight difference is documented** between `CLAUDE.md` content and a hook's text: both are
  context the model "tries to follow"; `CLAUDE.md` comes as a user message after the system
  prompt, a hook's text as a system reminder.
- **Imports outside the project** ask for approval once per project (current docs); the prototype
  team saw them skipped silently on 2026-10-15.
- **Skill directories are watched**: a skill added or changed under `~/.claude/skills/` or the
  project's `.claude/skills/` is picked up within the running session.
- **An import in `CLAUDE.md`** means writing into the user's project: a folder to create, a line in
  a file the team may keep in git, and both to clean up when the project is unlinked.
- **Skills** in Claude Code are files: a plugin's own (fixed per release), `~/.claude/skills/`, or
  `.claude/skills/` in the project. Skills that change with the Team would have to be written to
  one of the last two.

## How the prototype team does it (read 2026-10-21)

The prototype team keeps a rules hub in git; each developer clones it into a hidden folder in the
root of their home project, outside the project's git. A connect script does the rest once:

- **Rules** (seven files, ~48 KB together, ~12k tokens): short duties needed in every session,
  imported into the project's `CLAUDE.md` with `@<folder>/rules/<file>.md` lines, one per rule. A
  rule's form: the thesis; "When"; "What to do"; "Why"; "More", a link to the section of the team's
  wiki page where the full case with its date lives.
- **Skills**: linked from `~/.claude/skills/`, so they apply in every project on that computer.
- **Reference** (~60 KB: tool usage, tracker mechanics, onboarding): not loaded; rules and skills
  point at it by path and the agent reads it when needed.
- **Updating**: a SessionStart hook fast-forwards the clone and prints the titles of new commits.
  Imports load before the hook runs, so a changed rule acts in full from the next session; the
  hook says so.
- **The clone sits inside the project** because Claude Code silently skips an import of a file
  outside the project unless a separate permission is set, and the dialog that sets it is not
  shown (checked by the team on 2026-10-15, Claude Code 2.1).
- **A check after connecting**: a fresh `claude -p` session is asked whether it sees the rules.
- Changes to the hub go by merge request; the lead merges.

## Questions

1. **The channel.** The briefing at session start (comes back after compaction; 10,000 characters
   per hook); the local folder imported in `CLAUDE.md` as decided on 2026-10-16; or files the
   plugin keeps in the project's `.claude/rules/`, loaded by Claude Code itself.
2. **What the first version carries.** Team rules only; Area rules; skills; reference material.
3. **How a rule is changed in the first version.** The owner edits in the web with versions and a
   diff, or the full path by a Topic with an approved Outcome.
4. **Area rules that must reach a session before it enters the Area** ("before a release, look at
   Releases"): a part of the Area shown at session start, or such rules belong to the Team's set.
5. **Size.** Every session reads the whole set at start and after each compaction: is there a
   limit, and what happens past it.
6. **Coloqo's own rules and the Team's**: one text or two, and which wins when they disagree.
7. **Import and export** for a team that keeps its rules in git.

## Decided

- **Question 1, the channel (2026-10-21).** Coloqo is the source of the rules, with versions; the
  plugin delivers them: at session start it asks the server for the current version and, when it
  is newer, rewrites the project's `.claude/rules/coloqo/`, excluded from git by
  `.git/info/exclude`. Claude Code loads the folder itself and re-injects it after compaction; no
  line in `CLAUDE.md`, nothing in the team's `.gitignore`. A changed rule acts in full from the
  next session or compaction; the hook says the rules changed. No git on the member's side and no
  git hosting in Coloqo: storage, history with diffs, review (a Topic approved by the owner) and
  delivery are Coloqo's. Teams that keep rules in their own git are question 7.
- **Shown in the web (2026-10-21).** A "Rules" section on the Team page and on each Area: a tree
  of files by kind on the left, the chosen file rendered as Markdown on the right (a skill's
  script as code); the header names the version, who approved it, when and by which Topic.
  "History" lists the versions, each with its diff to the previous one and the Topic. One version
  number for the whole set, like a commit: a change touching several files is one diff. Every
  member of the Team sees it.
- **Question 2, what the first version carries (2026-10-21): all four kinds**, so the prototype team
  can move its hub whole instead of keeping half of it in git. Team rules go to
  `.claude/rules/coloqo/`; skills to the project's `.claude/skills/<name>/`, excluded from git;
  reference to a folder outside `rules` (e.g. `.claude/coloqo/reference/`), not loaded, read by
  path; Area rules come with the Topic, as decided on 2026-10-16. A skill's script is delivered,
  never run by the plugin; it is not singled out by a ban, but a changed script stands out in the
  history. To check before building: whether Claude Code finds skills in a nested
  `.claude/skills/coloqo/<name>/`.
