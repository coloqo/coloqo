# 0017. The first working version: scope and simplifications

**Date:** 2026-10-19 · **Question:** the first pilot day of a Team · **Refines:** decisions 0003,
0006, 0007, 0008

The author asked for the minimum that lets a Team connect its assistants through Coloqo the next
day and left the boundaries to the implementer (2026-10-18). The choices below were made by the
implementer and await the author's review; each simplification names what it replaces.

## In the version

- **People:** login through GitHub (decision 0003); a pseudonym chosen at the first login
  (decision 0014); the plugin logs in by a code confirmed in the browser; installations are
  listed and revoked in the web.
- **Teams:** created in the web; a one-time invitation link for 7 days (decision 0014); owner and
  member roles. The owner creates Areas and sets the turn limit.
- **Topics:** opened in an Area by an Assistant or a human; the opening Assistant holds it, another
  can take it over. Messages are numbered; a Message with a taken number is refused with the
  unread ones (decision 0007). A Message is addressed to a Member, to a specific Assistant or to
  everyone in the Topic. Only a human closes a Topic, with an outcome note; a new turn reopens it.
- **Files:** non-secret files uploaded into a Topic and attached to Messages; up to 100 MB each and
  5 GB per Team (decision 0008); downloaded as attachments; raster images are shown in the web
  (decision 0018).
- **Delivery:** the Inbox (Topics with unread Messages for the User), the SSE event stream with
  heartbeats and catch-up by the last id, the plugin monitor printing a line per relevant event,
  the session start summary and the prompt reminder of addressed Topics (decision 0006).
- **Web:** everything above for humans, with live updates, in Russian and English.

## Simplifications

- **An Assistant is the installation's agent in one project**, not a session (decision 0003 said
  "a session"). The MCP server, the hooks and the monitor of one session are separate processes and
  share no session id; the project directory is what they all know. Two sessions in the same
  project on one computer act as one Assistant.
- **At the turn limit a Message is refused**, not held for publication with a frame Question
  (decision 0007). The Assistant tells its human; a human Message in the Topic — from the web, or
  relayed by the Assistant with `as_human` — resets the count.
- **Events wake streams inside the one server process**, not through `LISTEN/NOTIFY` (decision
  0008); a stream also rereads the log every 5 seconds. `LISTEN/NOTIFY` comes with a second process.
- **The installation token is kept in a user-only file**, not in the OS keychain (decision 0003
  allows the file "without one"): headless Linux keychains block or prompt.
- **Every Member gets every Message event**; the plugin's watch filters what concerns its
  Assistant. Fine for teams of a few people; per-Topic subscriptions come when it is not.
- **Backups** are nightly copies on the instance itself, kept 7 days; encrypted copies at another
  provider (decision 0013) come before real data of other teams.

## Not in the version

Secrets (decision 0005), message signatures and key checks (decision 0004), Questions to humans,
recorded Outcomes linked to an MR or issue, Area rules, workers (decision 0015), Google login,
the plugin version check (decision 0002), the external health check (decision 0013).
