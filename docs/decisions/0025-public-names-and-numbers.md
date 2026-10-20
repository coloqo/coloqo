# 0025. Public names and numbers: slugs, per-Team numbering, addresses

**Date:** 2026-10-20 · **Question:** database ids showed in addresses, links and committed files,
and one Team's Topic numbers jumped over the Topics of other Teams · **Refines:** decisions 0006,
0007, 0010, 0020

Teams, Areas, Topics, files and Assistants were known outside the server by their database ids:
`/teams/3`, `?area=7`, `/topics/41`, `[file 41]`, `/assistants/17/link`, and `{"team_id": 3}` in
the `.coloqo.json` that teams commit. A stranger gets 404, so the ids opened nothing, but they
showed how many Teams, Topics and files an instance holds, and read as the database's insides.
`T-41` was the Topic's id shared by every Team, so a Team's Topics were numbered with gaps. The
author asked for readable addresses and numbering that starts at 1 in each Team. The working file
is `docs/tasks/2026-10-20-web-look-and-numbering.md`, points 5 and 6.

## Decision

**No database id leaves the server.** Inside, the numeric keys stay: they hold the relations, and a
rename must not rewrite every row that points at a Team.

**A Team has a slug**, `acme`, its only public identifier, in the web, the API and `.coloqo.json`
(`{"team": "acme"}`).

- It is offered from the Team's name when the Team is created, transliterated when the name is
  not Latin ("Платёжный сервис" → `platyozhnyy-servis`); the owner can edit it. Lowercase Latin
  letters, digits and hyphens, unique on the instance; when taken, `acme-2` is offered.
- The owner can change it. Former slugs keep leading to the Team, so links in MRs and trackers and
  committed `.coloqo.json` files do not break.
- A slug as the database key was weighed: it fits only a slug that never changes, and a fixed slug
  would keep a typo or a former name in every address.

**An Area has a slug within its Team**, the same way: `releases`.

**Topics are numbered per Team, from 1, without gaps.** The Team keeps a counter; a new Topic takes
the next number under a lock on the Team's row, as Messages are numbered in a Topic (decision 0007),
so a rolled-back transaction loses no number. A deleted Topic keeps its card (decision 0021), so its
number stays taken.

**Files are numbered per Team too.** When a Topic's conversation is deleted its files go and their
numbers stay taken: file numbers may have gaps, they are never given twice. The same series will
number a Team's files outside Topics (reference material, question 11 of the product statement). A
file is reached only by those who may read its Topic.

**Addresses use lowercase only**, in the code and the documentation, and put every Team under
`/team/`:

| Address | Opens |
|---|---|
| `/team/acme` | the Team |
| `/team/acme/area/releases` | an Area |
| `/team/acme/topic/12` | a Topic |
| `/team/acme/topic/12#m-5` | a Message in it |
| `/team/acme/file/3` | a file (shown, or saved with `?download=1`) |

The API mirrors the pages, in the singular: `/api/team/acme/topic/12`, `/api/team/acme/file/3`.
`/acme/t12` and `/acme/topic12` were weighed: they put Topics on the level of Area slugs and would
forbid Area slugs like `t1000-migration`. A Team at the root (`/acme`) was weighed too: it needs a
list of reserved words, and every page added later could collide with a Team that already exists.

**References in text** stay `T-12` and `file 3`, as people and agents say them. In an agent's
tools they mean the Team the project is linked to; another Team's are `globex/T-12` and
`globex/file 3`. In an MR or a tracker the agent writes the full link
(`https://app.coloqo.team/team/acme/topic/12`), or at least `acme/T-12`; the briefing says so.

**Linking an Assistant to a Team** in the browser opens by a one-time random token, not by the
Assistant's id.

**The change keeps the data.** A migration gives each Team a slug from its name and each Area a
slug within its Team, and numbers the Topics and files of each Team from 1 in their old order. The
paths of plugin 0.4.0 and its `.coloqo.json` (`team_id`) keep working for one more release, and the
briefing tells such a session to update the plugin; the release after removes them.

## Why

- A slug says which Team a link is about; a number says how many Teams there are.
- A changeable slug with its former ones kept is what people expect from an organisation's address
  and does not break what was already pasted into trackers.
- People read Topics in order and talk about them by number: a Team's own series from 1 reads as
  the Team's, not the instance's.
- A `/team/` prefix and a word per kind of page keep every kind of address apart without reserved
  words, now and for pages added later.
