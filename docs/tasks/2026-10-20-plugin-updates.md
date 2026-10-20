# The plugin keeps itself up to date: the user does not have to

## What happened

2026-10-20, releasing coloqo 0.4.0 (decision 0023). The Claude Code plugin reaches users through
the `coloqo` marketplace in this repository; its `plugin.json` version names the release, and its
hooks, MCP server and watch pin the PyPI package to the same version. Claude Code's auto-update is
off by default for third-party marketplaces, so each member of the pilot team has to run
`/plugin marketplace update coloqo` (or `claude plugin update coloqo@coloqo`) and restart. The
author updated by hand until now. A member who does not stays on the old hooks and rules.

The plugin already sends its version with every request (`X-Coloqo-Plugin`); the server ignores it.

## Facts checked (2026-10-20)

- Claude Code computes a plugin's version from `plugin.json` (then the marketplace entry) and
  updates only when it changes; auto-update is off for third-party marketplaces, a user turns it on
  in `/plugin` → Marketplaces → Enable auto-update, an administrator through managed settings.
  The CLI has no flag for it.
- `claude plugin marketplace update coloqo` and `claude plugin update coloqo@coloqo` are CLI
  commands with `--json`; the update applies after a restart (`/reload-plugins` or a new session).

## Direction (accepted 2026-10-20)

1. **Auto-update on at install.** The install steps (README, `uvx coloqo login`) ask the user once
   to turn on auto-update for the `coloqo` marketplace.
2. **The server tells, the agent updates.** The server knows the latest plugin release and reads
   `X-Coloqo-Plugin`; when the session's plugin is older, the briefing tells the agent to run the
   two commands and to tell the user that the new version applies from the next session.

Not taken: unpinning the package (`uvx coloqo@latest`): a PyPI round trip on every hook start, no
reproducibility, a release reaches everyone unchecked, and `hooks.json` changes still need the
plugin updated.

## Decided 2026-10-20 (the author, before leaving for the day)

- **The latest release** comes from PyPI: the server asks now and then (about once an hour) and
  keeps the answer. When PyPI cannot be reached, as on a self-hosted instance without the
  internet, there is no hint.
- **The agent updates by itself and tells the user** in one line that the new version works from
  the next session.
- **The order:** after the documentation, the one change of the data model and the web.

## Still open

- What the briefing says and when: every session start while outdated, or once; does an outdated
  plugin ever get refused (a minimum version)? Until decided: every session start while outdated,
  never refused.
- A self-hosted instance: its own marketplace or the public one.
- Whether a project's committed `.claude/settings.json` can declare the marketplace with
  auto-update on (unchecked).

## Found on the way

- The watch prints "Coloqo: connection restored after N min; check the inbox." in a project that
  is not linked to a Team (seen 2026-10-20 in this repository), while decision 0020 says such a
  project stays quiet. `watch.py` reports the restored connection without looking at the link.
