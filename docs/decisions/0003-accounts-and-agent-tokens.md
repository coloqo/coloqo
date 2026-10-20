# 0003. Accounts, login and installation tokens

**Date:** 2026-10-16 · **Question:** A3, `docs/architecture/architecture.md`

**Refined by decision 0015** (2026-10-17): workers. **By decision 0020** (2026-10-19): a project's Assistant is linked to one Team. **By decision 0024** (2026-10-20): an Assistant is a session; the link to a Team belongs to the computer × project.

## Decision

- **A human logs in through external providers** — GitHub and Google. Coloqo has no passwords
  of its own.
- **The plugin gets the right to act through device code login**, like `gh auth login`: the
  human starts login in the plugin, sees a short code and confirms it in the browser under their
  account. The plugin receives an **installation token** bound to the User and the computer.
  Installations are visible to the human in the web interface, and each can be revoked
  separately. The token is kept in the OS keychain, and without one — in a file readable only
  by the owner.
- **An Assistant is a Claude Code session on an installation.** The plugin registers the
  Assistant at session start with a default name from the project (`alice · billing-api`); the
  human can rename it. The Inbox is shared by all of a User's Assistants; a specific Assistant
  is called by name.
- **The server checks human-only actions.** The installation token does not have these rights:
  a call that bypasses the tools is refused. Confirming an Outcome, invitations, approving rule
  edits — only from the human's web session.
- **Authorship** — on every message: the User and the Assistant's name, or "human" for what is
  written from the web interface.

## Why

- Without passwords of our own there is nothing to store, reset or protect from brute force.
- A token per computer, not per User: a lost computer is revoked, the others keep working.
- A missing tool is a hint to the model, not protection; the rights boundary is held by the
  server.
