# 0029. Online sessions, and whom a Message to a session reaches

**Date:** 2026-10-21 · **Question:** the web lists every session of the last day with no sign of
which run, and a Message addressed to a session that is gone reaches nobody's attention ·
**Refines:** decisions 0006, 0024

Each Claude Code session is an Assistant (decision 0024). The Team page listed every Assistant seen
within 24 hours with "last seen", the time of its last request; a running session the user left
alone looked hours old, and a session ended by `/clear` stayed listed for a day. A colleague's
Assistant answered a question one of the author's sessions had asked, addressed to that session; the
session was gone, the watch of every other session dropped the Message as another session's, and the
author learned of it only at their next prompt. The working files are
`docs/tasks/2026-10-21-which-assistants-are-live.md` and
`docs/tasks/2026-10-21-addressed-to-a-person-via-a-session.md`.

## Decision

**A session is online while its watch runs.** The watch lives as long as its session. It tells the
server every 20 seconds, and a session that made a request within the last minute is online; the
minute covers a missed call and a restart of the server. *Found while building it, 2026-10-21:* the
open stream alone cannot tell, because a laptop closed with a session running leaves the stream open
on the server's side until TCP gives up, for many minutes, and a Message would go to the sleeping
session all that time.

**Offline for 20 minutes, a session is forgotten**: no list shows it. A session that comes back, a
laptop waking and its watch reconnecting, is shown again. The web marks an online session with a
steady green dot with a soft glow, an offline one with a grey dot and a faded line with its last
request. The Team page, the user's own list of sessions and the names offered for an unknown
addressee show the same sessions. The idle warning's "holder is live" means its session is online.
A session's word stays its own for 24 hours as before, so a Topic's old Messages do not mix two
sessions of one name.

**A Message to a session that is not online goes to its person**, when it is sent, with a mark: it
was meant for that session, which is offline. Every online session of the person sees it as
theirs, with the mark; with none online, it waits in the person's Inbox and in the web. The sender
is told in the answer to its post. The first Message of a Topic is addressed the same way.

**A Message to an online session is that session's**, and the person's other online sessions see it
as a quiet line, "a message for chime from mirach in T-12; chime answers it", filtered by the focus
as any event. The person learns there is a question and where; an Assistant knows it is not its own
and does not answer for another session. The prompt hook and the Inbox mark it the same way.

**Assistants address the person by default**, and a session only when the question is about that
session's own work (`post_message`).

**Weighed.**
- Readdressing a Message when its session is forgotten, 20 minutes after it went offline, by a job
  every minute: the person would learn of it 20 minutes late, and nothing needs to wait.
- Showing every Message to a session only to that session: the question waits in a window the person
  is not looking at.
- A blinking green dot: dropped by the author; a steady one says the same.

## Why

- The addressee of a question is a person. The session that asked is how the sender knows them, not
  which of their windows should hear.
- Sessions are short and replace each other; an answer that comes hours later usually finds the
  asking session gone.
- A list of sessions is useful only if it tells which run.
