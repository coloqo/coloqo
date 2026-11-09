# Updates reach sessions and people at once

## What happened

2026-11-08 … 2026-11-09, the prototype team. The lead's session started on 2026-11-08 at 11:56
with plugin 0.6.0. The same day 0.7.0 and 0.8.0 came out with the task tracker: tasks, a board,
promises, free Topics. The session kept running on 0.6.0 for a day without the task tools. It learned about the release from the author, who had seen
the new web; opening `/plugin` in the interface did not update anything either. The assistant then
ran the two commands of decision 0027 by hand: 0.6.0 → 0.8.0, "Restart to apply changes".

The author: "no guessing: I want updates in Coloqo to be visible to users at once, through the
connection to the server."

## Facts checked (2026-11-09)

- **The hint comes only at session start** (decision 0027): the server compares the session's
  `X-Coloqo-Plugin` with the latest release on PyPI (asked once an hour, `releases.py`) and puts the
  line into the briefing (`briefing.update_hint`). A session that started before a release never
  gets it: a working session lives for days and goes through compaction without a new start hook.
- **The session is already connected all the time.** `watch` holds `/api/events` and calls the
  server every 15 s with the plugin's version in the header (decision 0029); the server knows both
  the session's version and the latest one at any moment.
- **Old `watch` shows only the kinds it knows.** In 0.6.0 `describe()` handles `topic` and
  `message`; any other kind is dropped silently. A new event kind reaches only plugins that know it.
- **Updating does not change the running session.** Claude Code loads the plugin at start; the MCP
  server and the hooks are pinned to `uvx coloqo@<version>`. After the update the session keeps
  the old tools and rules until it restarts.
- **Auto-update of the marketplace was off** on the author's machine: `known_marketplaces.json` has
  no auto-update for `coloqo`, as decision 0027 feared; `/plugin` did not refresh the marketplace
  clone.
- **Not every update is the plugin.** The tracker was a server release too: the board and promises
  appeared in the web at once, the briefing's rules changed on the server, and a running session
  learned nothing of it.

## Proposal (to discuss)

1. **An `update` event on the stream.** The server sends it to a session whose plugin is older than
   the latest: right after `ready`, and when the hourly PyPI check finds a new release. `watch`
   prints a line; the Assistant runs the two commands at once and tells its user in one line what
   is new and that it works after a restart.
2. **What is new, in words.** The event carries a short text of the release for people (the
   tracker: tasks, a board, promises, free Topics), not only the version number; the same text
   goes to the start hint.
3. **Server releases are announced too.** When the server's version changes, every live session
   gets the same kind of line: what changed for the Assistant (new rules in the briefing, new tools
   after the update) and for people (new pages in the web).
4. **People in the web see it as well**: a line "What's new in Coloqo" after a release, and on a
   member's page which of their sessions run an old plugin.

## Questions, one at a time

1. **Where the text of a release comes from:** a section in the repository (a changelog), the
   GitHub release, or a field the author fills on the server?
2. **Plugins already installed** (≤ 0.8.0) drop a new kind. Is it enough that they learn once more
   from the start hint, or should the first notice reach them through a kind they render (a
   `message`)?
3. **Restart:** is "works after a restart" enough, or should the Assistant offer the user to restart
   the session right away and say how to resume?
4. **Server releases:** announce each one, or only those marked as visible to users?
5. **Auto-update of the marketplace:** keep asking the user to turn it on at install (decision 0027),
   or have the start hook check and remind while it is off?
