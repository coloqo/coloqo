# 0010. Web interface and server: one codebase, deployment by configuration

**Date:** 2026-10-17 · **Question:** A10 (packaging part), `docs/architecture/architecture.md`

## Decision

- **The contract is already separate.** The web interface is an API client just like the plugin:
  everything goes through REST described by OpenAPI (decision 0002); the server does not know who
  calls it.
- **One repository.** The frontend is a separate directory with its own toolchain; its build
  output is static files, not a process.
- **Deployment differs by configuration, not by code.**
  - Self-hosted edition: the server serves the static files itself — one container.
  - Cloud: the same single container in the pilot (revised 2026-10-18, decision 0016: the
    server wheel with the web inside, no container); later the static files go through a CDN or
    nginx, and the API scales separately (long-lived SSE connections).
- **One address.** `/` — static files, `/api` — the server; a reverse proxy routes them.
  Different domains would bring CORS and cross-site cookies into the web login.
- **The product site** (landing page, pricing, cloud sign-up) is not the Coloqo interface; it
  belongs in the closed cloud part (decision 0009).

## Why

- An API change touches the contract, the server and the interface together: in one repository
  it is one commit, reviewed as a whole; in two — two MRs, version coordination and a window of
  divergence. A separate repository is justified by a separate web team or its own release
  cadence.
- This is how GitLab is built: the Vue web interface is in the same repository as the server; the
  group of projects around it are separate programs (Gitaly, Runner, Omnibus), not halves of the
  application. Open WebUI serves its built interface from its server in one image.

## Open

The scope of the first version's web interface and the frontend technology — the rest of
question A10.
