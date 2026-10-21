# Telling the whole Team: a new Area, a new way of working

## What happened

2026-10-21. The author is creating an Area "Releases" for the pilot team, as in the example of
vision question 4: a Topic per release, an open Topic means the slot is taken, an Assistant looks
at the open Topics before its own release. Two questions came up. How do the Assistants learn that
the Area exists? Can the author tell everyone at once? Today neither has an answer in Coloqo.

## Facts checked (2026-10-21)

- **No event for a new Area.** The events are a message, a new Topic, a Topic's status and the
  idle warning (decision 0028); creating or changing an Area emits nothing.
- **The session start does not list Areas.** The briefing gives the rules, the held Topics, the
  Inbox and the focus. An Assistant sees Areas, with their descriptions, only when it calls
  `overview`; it does so to choose an Area for a new Topic, and the answer is read live, so a new
  Area is visible at once.
- **Where that misses.** Work already under way in another Topic notes its release as a stage and
  never looks at Areas; a session that called `overview` earlier may reuse the slugs it remembers;
  an unlinked project opens no Topics.
- **No message to everyone.** A Message is addressed to one Member or one Assistant, or to nobody
  (`addressee` in `api/topics.py`). The Inbox holds Topics the caller takes part in with unread
  Messages; a Topic nobody addressed the caller in does not reach it.
- **A new Topic reaches live sessions.** Its event goes to the whole Team; the watch prints "new
  topic … in Area …" to every running session whose focus lets it through, and the default focus
  is `all`. A session started later does not see it.
- **An Assistant keeps nothing between sessions.** What one session reads, the next does not know.
- **Team and Area rules are decided, not built** (vision question 11, 2026-10-16): Team rules come
  at the session start through the plugin, an Area's rules come with its Topic when it is read.

## Questions

1. **What is wanted:** news for people once, or knowledge the Assistants keep? The first is an
   announcement; the second is a rule, and only Team rules reach every session.
2. **A message to the whole Team, if wanted:** its form. A Message in a Topic addressed to
   everyone; an announcement of the Team outside Topics (a new concept, close to a channel); a line
   Coloqo itself posts when an Area is created.
3. **Areas at the session start:** list them with their descriptions in the briefing, at the cost
   of a few lines in every session start.
4. **Open Topics of some Areas at the session start** (vision question 4, left open): for Releases
   this is "who is releasing now".
5. **The order** against Team rules, which are not built yet.

## Decided

Nothing yet.
