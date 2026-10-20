# 0027. The plugin keeps itself up to date

**Date:** 2026-10-20 · **Question:** members of the pilot team stayed on old plugin versions unless
they updated by hand · **Refines:** decisions 0011, 0021

Claude Code updates a plugin when its `plugin.json` version changes, but auto-update is off by
default for third-party marketplaces such as `coloqo`. A member who does not run
`/plugin marketplace update coloqo` stays on the old hooks, rules and pins. The plugin already sends
its version with every request (`X-Coloqo-Plugin`). The working file is
`docs/tasks/2026-10-20-plugin-updates.md`.

## Decision

- **Auto-update on at install.** The install steps (README, the connect page and its text for an AI,
  decision 0026) ask the user once to turn on auto-update for the `coloqo` marketplace in `/plugin`
  → Marketplaces. The CLI has no flag for it.
- **The server tells, the agent updates.** The server learns the latest release from PyPI, asking
  about once an hour and keeping the answer; without PyPI, as on a self-hosted instance without the
  internet, it gives no hint. When a session's plugin is older, the briefing tells the agent to run
  `claude plugin marketplace update coloqo` and `claude plugin update coloqo@coloqo` and to tell the
  user in one line that the new version works from the next session. The agent does it on its own.
- Until decided otherwise, the hint comes at every session start while the plugin is outdated, and
  an outdated plugin is never refused.
- Unpinning the package (`uvx coloqo@latest`) was weighed and not taken: a PyPI round trip on every
  hook start, no reproducibility, a release reaching everyone unchecked, and `hooks.json` changes
  would still need the plugin updated.

## Why

- Rules, hooks and the server move together; a member left on an old plugin works by old rules
  without knowing it.
- The update is two shell commands the agent can run; the user should not have to remember them.
- PyPI already knows the latest release; a setting kept by hand would be forgotten.
