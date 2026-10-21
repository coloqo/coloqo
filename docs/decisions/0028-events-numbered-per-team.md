# 0028. Events are numbered per Team

**Date:** 2026-10-21 · **Question:** the event stream's cursor is a database id from one sequence
for the whole instance, against decision 0025 · **Refines:** decisions 0006, 0008, 0025

An event was written once for each member of its Team, as a row of `events` with an id from one
sequence for all Users, and that id went to the client as the SSE `id:` and came back as
`Last-Event-ID`. Between two of their own events a User saw how many events everyone on the
instance had received meanwhile: the activity of other Teams. Decision 0025 says no database id
leaves the server; the cursor was found to break it while building 0025.

## Decision

**An event belongs to a Team and takes the Team's next event number**, from 1, without gaps, under
a lock on the Team's row, as Topics and files are numbered (decision 0025). It is stored once, not
once per member. Every event today is a Team's (a message, a new Topic, a Topic's status), and the
same for each member, so each member sees every number of their Teams and nothing else.

*Found while building it, 2026-10-21; decided by the author the same day.* One event was not the
whole Team's: the warning that a Topic closes for inactivity (`topic_idle`) went to the Topic's
people and its holder's person. It now goes to the whole Team like every event. Nothing visible
changes: the web ignores it, and the plugin shows it to the holder's sessions alone, as before. A
numbering of one's own (`me:`) was weighed: it suits events meant for one person, and this one
was shown to the holder only anyway.

**The cursor names a number per Team**: `acme:120,globex:45`, sent as the SSE `id:` and returned as
`Last-Event-ID`; the heartbeat (decision 0006) carries the same. A browser follows all its User's
Teams; a session's plugin follows the one its project is linked to (decision 0020), so its cursor
has one part. A Team missing from the cursor starts from its current number: a client that had
no cursor, or a Team joined while it was away. A Team the User has left is dropped.

*Found while building it, 2026-10-21; confirmed by the author the same day.* A Team joined
while the stream is open starts from the member's joining, not from its current number: the
first event after joining is what wakes the stream, and the current number already counts it, so
it would be lost.

**Events for one person**, when some appear (an invitation, a notice to one member), get a
numbering of their own, as the `me:7` part of the cursor. There are none now.

**The change starts the log anew.** The log is kept for a week and is a signal to re-read, not
content (decisions 0006, 0008), so it is not carried over. A client reconnecting with an old
numeric cursor, plugins 0.3 and 0.4 among them, gets new events only and re-reads, as a client
gone longer than the log does.

**Weighed.**
- An exception in decision 0025 for an opaque cursor: nothing to build, and the leak stays.
- A numbering per User: one row per recipient as before, and a counter per User locked for every
  member at every event.
- An encrypted id: no migration, but a server key to keep; losing or changing it invalidates every
  client's cursor at once.

## Why

- A Team's members see its events anyway: their numbers tell nothing the web does not show.
- The same rule as for Topics and files: a public number lives in its Team's series, the database
  id stays inside.
- One row per event instead of one per member: the log shrinks by the size of the Team.
