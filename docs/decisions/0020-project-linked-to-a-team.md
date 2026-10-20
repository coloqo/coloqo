# 0020. A project is linked to one Team

**Date:** 2026-10-19 · **Question:** a session in a project unrelated to a Team still joined it ·
**Refines:** decisions 0003, 0006

**Refined by decision 0024** (2026-10-20): the link belongs to the computer × project. **By decision 0025** (2026-10-20): `.coloqo.json` names the Team by slug.

The plugin is installed for a person, so it runs in every project they open. At session start
it registered an Assistant for the project, and that Assistant saw all of the person's Teams:
a session working on Coloqo itself got the pilot Team's Inbox, reminders and notifications,
and could write there. The author asked for a project to be tied to its Team.

## Decision

**Where the link lives.** The server keeps it on the Assistant (`assistants.team_id`; an
Assistant is an installation plus a project, decision 0003) and enforces it. A file
`.coloqo.json` committed in a repository links its projects without anyone's action:

```json
{ "team_id": 1, "team": "Acme" }
```

`team` is for people reading the file; the id alone opens nothing.

**One Team per project.** Writing then never asks where to go. A repository that two Teams
work with is rare: the second Team is written to from the web, or the project is relinked. If
it becomes common, the file can grow a list next to `team_id` without breaking.

**What an Assistant may do.**

| | Linked project | Unlinked project |
|---|---|---|
| **Brought into the session:** Inbox at start, reminders, the watch | its Team only | nothing |
| **Reading on request:** overview, Topics, Messages, files | all of the person's Teams | all of the person's Teams |
| **Writing:** open a Topic, post, hold, upload | its Team only | refused until linked |

- Reading crosses Teams because a person may need material from another Team's conversation in
  the project at hand; it happens only when they ask, and the plugin's instructions say so.
  Reading outside the linked Team does not mark Messages read: the person looked something up,
  they did not go through that Team's Inbox.
- Writing is what other people see, so the server allows it only in the linked Team. A request
  that names no Assistant (the installation token alone) gets no Team data.
- The web, where the person is logged in themselves, is unchanged.
- The Inbox stays one per person (decision 0006); each Assistant sees the part of it in its
  Team.

**An unlinked project is quiet.** No Inbox at start, no reminders, no notifications. The session
start tells the model in one line that Coloqo is off for writing here and how to link; it
mentions it only if the person brings Coloqo up. The session does not ask on every start: the
answer would have to be remembered per folder, and quiet with a hint gives the same.

**Linking.**

1. **The file.** At session start the plugin sends the file's `team_id` with the registration.
   The server links the Assistant if the person is a member of that Team and the Assistant is
   not linked yet. It never overrides an existing link: changing it is the person's decision.
2. **`uvx coloqo link`** (or `/coloqo:link`) for a project without the file, confirmed in the
   browser like the plugin's login: the page offers the person's Teams, the person picks one.
   The model cannot link or relink itself silently. Afterwards the command offers to write
   `.coloqo.json`; committing it is the person's call.
3. **The web settings** list the Assistants (computer and project) with their Teams; an
   Assistant is unlinked or moved to another Team there.

**Existing Assistants.** The migration links an Assistant that wrote Messages or held Topics in
exactly one Team to that Team. The others stay unlinked and quiet until linked: one that never
wrote anywhere, or wrote in several Teams.

## Why

- A Team's conversations should reach only the sessions that work for that Team. Anything that
  arrives unasked, or a Message written into the wrong Team, is a leak in one direction or the
  other.
- The rights boundary is held by the server (decision 0003): a file in a repository or an
  instruction to the model only suggests.
- Reading on request across Teams is what a person does in the web anyway; forbidding it to
  their Assistant would only push them to copy text by hand.
- Linking through the browser keeps the choice with the person, as the plugin's login does.
