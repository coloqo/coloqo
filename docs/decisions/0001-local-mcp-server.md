# 0001. The MCP server runs locally, as part of the plugin

**Date:** 2026-10-16 · **Question:** A1, `docs/architecture/architecture.md`

## Decision

The Coloqo MCP server runs on the User's computer as part of the plugin (stdio). The cloud
provides an ordinary API; the MCP server, the session start hook and the watch call it the same
way.

## Why

- Encryption and keys are on the client side (product statement, question 8). An agent would
  pass a secret to a remote MCP server as a tool argument, and the server would see it.
- The local server takes a file path and sends the file itself. With a remote server the agent
  would have to pass the content as an argument — through its own context: expensive, and a
  large file does not fit.
- The plugin is installed anyway (skill, hook, watch); a local server adds no new installation.

## Cost

New tools arrive with a plugin update, not immediately from the server.
