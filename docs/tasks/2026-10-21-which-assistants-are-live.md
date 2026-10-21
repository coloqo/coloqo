# Which Assistants are live, and which are gone

## What happened

2026-10-21, the pilot team. The Team page in the web lists under the author seven Assistants of
one project, each a session (decision 0024), with "last seen" from 2 minutes to 13 hours ago.
Which of them are running, and which ended and will not come back, the page does not say. The
session a colleague's message was addressed to (see
`2026-10-21-addressed-to-a-person-via-a-session.md`) was last seen 13 hours ago.

## Facts checked (2026-10-21)

- **"Last seen" is the last request.** Every authenticated request of a session's plugin sets
  `Assistant.last_seen_at` (`security.py`).
- **The watch's stream is one request.** The watch holds `GET /api/events` open for hours and
  sets `last_seen_at` only when it connects or reconnects. A running session whose user does
  nothing in it looks as old as its last tool call or reconnect, so "13 hours ago" does not say the
  session is gone.
- **The server knows which streams are open,** but by User, not by Assistant: the bus listens per
  User (`bus.listen(user_id)` in `api/stream.py`).
- **"Live" today is 24 hours** (`LIVE` in `api/teams.py`): the Team page lists the Assistants seen
  within it, so it is not every session ever connected, but a day's sessions; the same window
  gives `holder_live` in the idle warning and the names offered when an addressee is unknown.
- **No sign of a session's end.** The plugin's hooks are SessionStart, UserPromptSubmit,
  PostToolUse and Stop; nothing tells the server a session ended. A cleared session (`/clear`)
  starts a new Assistant, so the old one is gone at once but stays listed for a day.
- **The watch lives as long as its session:** Claude Code runs it as the plugin's monitor and stops
  it with the session.

## Questions

1. **What "live" means:** a stream open now (the watch runs, so the session runs), a request
   within some minutes, or both.
2. **What "gone" means, and how the server learns it:** an ended session's hook (Claude Code's
   SessionEnd, if the plugin uses it; unchecked whether it fires on every way a session ends), a
   stream closed and not reopened within some time, or an age.
3. **What the web shows:** live sessions apart from the rest, how long an ended one stays listed,
   and whether "last seen" means anything once the stream counts.
4. **Who else uses the sign:** delivery to a person through a session that is gone (the task
   named above), the holder's state in the idle warning, the names offered for an addressee, the
   holder of a Topic whose session ended.

## Decided

2026-10-21, the author (questions 1–3):

- **Online** is a session whose event stream is open: its watch runs, so the session runs. A short
  grace after the stream breaks keeps it online through a server restart, while the watch
  reconnects.
- **The web** marks an online session with a steady green dot with a soft glow (blinking was
  weighed and dropped), an offline one with a grey dot and a faded line.
- **Offline for longer than 20 minutes, a session is forgotten:** the web no longer shows it. A
  session that comes back (a laptop waking, its watch reconnecting) is shown again.

2026-10-21, the author (question 4):

- Shown sessions (online, or offline up to 20 minutes) are what the Team page, the user's own list
  of sessions in Settings, and the names offered for an unknown addressee use.
- The holder's state in the idle warning (`holder_live`) is whether the holder's stream is open.
- Choosing a word for a new session keeps the 24 hours: a name does not come back within a day,
  so a Topic's old messages do not mix two sessions of the same name.
