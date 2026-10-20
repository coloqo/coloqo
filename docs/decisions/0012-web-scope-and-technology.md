# 0012. Web interface: first version scope and technology

**Date:** 2026-10-17 · **Question:** A10 (the rest after decision 0010),
`docs/architecture/architecture.md`

**Refined by decision 0026** (2026-10-20): reading a Topic, the human's part in a Message, "For you".

## Decision

- **First version scope.**
  - Everything only a human can do: login and confirming the plugin's login code (0003); Teams —
    invitations, Areas, roles (question 5); confirming an Outcome and approving a rules change
    with a diff of versions (0003, question 11); installations — list and revocation (0003,
    0004); deleting Topics and Areas (0008); Team settings — turn limit, retention period (0007,
    question 8).
  - Reading Topics live through the same event stream; a human's reply in a Topic, manual pause,
    the list of open Questions (0006, 0007).
  - A layout that works on a phone: answering a Question away from the computer is a common case.
  - The web does not show the content of secrets: it has no keys, only the transfer state is
    visible (0005).
- **Not included:** search, email and push notifications, a pilot metrics screen (the measures of
  question 2 — by a database query or a script).
- **Technology:** React, TypeScript, Vite.
  - The API client is generated from OpenAPI (`openapi-typescript`, `openapi-fetch`).
  - Data — TanStack Query; components — Tailwind and shadcn/ui (copied into the repository).
  - Message Markdown — without HTML (react-markdown without raw HTML): the texts are written by
    Assistants, they are untrusted data.
  - Two languages, Russian and English, from the first version — react-i18next.

## Why

- The mandatory scope follows from human-only actions going through the web, not through the
  Assistant (decision 0003).
- Client from OpenAPI: the compiler catches divergence from the server.
- React, not Svelte: more ready-made components, best known to the agents writing the code, and
  easier to find helpers. Server-side HTMX contradicts decision 0010: the web is an API client.
- Strings extracted right away cost almost nothing; extracting them later means a pass over every
  screen.
