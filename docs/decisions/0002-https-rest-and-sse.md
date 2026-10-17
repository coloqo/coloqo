# 0002. Plugin and cloud: HTTPS with JSON and events over SSE

**Date:** 2026-10-16 · **Question:** A2, `docs/architecture/architecture.md`

## Decision

- **Requests** — HTTPS with JSON, REST: Topics, Messages, Inbox, transfers. The web interface
  uses the same API.
- **Events** — Server-Sent Events over HTTPS. The watch holds the stream and receives events,
  while the agent reads and writes through REST. When the connection breaks, the client
  reconnects with the number of the last received event and the server sends what was missed
  (the Inbox cursor — question A6).
- **Plugin version** — in every request. The response says whether a newer version exists and
  refuses with a clear error below the minimum. The model sees the update hint in the tool
  result, in the MCP server instructions and in the session start hook summary; the agent
  suggests the update to the human rather than installing it silently.
- **API description** — OpenAPI: a client for another agent can be built from it.

## Why

- The watch only needs a stream from the server to the client. Reconnection with catch-up is
  built into SSE (`Last-Event-ID`); with WebSocket the back channel is not needed, and
  reconnection and catch-up would have to be written by hand.
- REST with JSON is the easiest to debug, test and describe.
- Getting through a corporate proxy is not required (product statement, question 8).
