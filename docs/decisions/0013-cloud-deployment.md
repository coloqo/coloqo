# 0013. Cloud deployment

**Date:** 2026-10-17 · **Question:** A11, `docs/architecture/architecture.md`

**Revised 2026-10-18:** no `docker compose` on the cloud instance — a systemd service, Caddy and
later PostgreSQL from apt, the server from a GitHub Release built by CI (decision 0016).

## Decision

- **Domain — `coloqo.team`** (registered by the author on 2026-10-17, DNS at Timeweb).
  - `app.coloqo.team` — the cloud instance: web at `/`, API at `/api` (decision 0010).
  - `coloqo.team` — the product site, later; until then the root is free.
- **A separate VDS in Russia**, not shared with the author's other services. For the pilot —
  2 vCPU and 4 GB; the provider — for example, Timeweb Cloud, where the domain already is.
- **`docker compose`:** Coloqo (the image, decision 0011), PostgreSQL, Caddy (issues TLS
  certificates itself, proxies SSE). GitHub Actions builds the image and pushes it to GHCR; on
  the server — `docker compose pull && up -d`, migrations run at startup.
- **Backups:** every night `pg_dump` and the files volume; age encryption; stored in another
  provider's object storage; retention — 14 days, also stated in the terms of service
  (decision 0008). Before the pilot — one restore test on a clean machine.
- **Monitoring:** an external check of `/api/health` once a minute with a notification to the
  author; container logs with rotation; no metrics.
- **Web session protection** (the product site and the application are one site from the
  `SameSite` point of view):
  - session cookie `__Host-`, no `Domain`, `HttpOnly`, `Secure`, `SameSite=Strict`;
  - state-changing API requests — `Origin` header check and a CSRF token;
  - CORS — only `app.coloqo.team`;
  - the application's CSP — `script-src 'self'`, no third-party code.

## Why

- A public service on one machine with other services: compromising the public service must not
  give access to them.
- Russia: the primary database of personal data of Russian citizens is kept in Russia (Federal
  Law 152-FZ); other legal questions — M5 of the product statement.
- An application subdomain:
  - the server address is baked into plugin installations and OAuth callback addresses — the
    root is left to the site from the start, no move will be needed;
  - the browser isolates origins, not paths. Third-party scripts of the product site (analytics
    with session recording, tag manager, widgets, pixels, site builder) at the same address would
    read the application's storage and pages and call `/api` on behalf of the logged-in user; the
    web session is the strongest right (decision 0003). A supply chain example: in 2024 the
    `polyfill.io` domain changed owners and served malicious code to the sites that included it;
  - session recording on application pages would carry Teams' conversations off to a third
    party.
- `docker compose` and Caddy — nothing extra for one instance; Kubernetes and Helm — in the
  self-hosted edition (decision 0009).
- Backups at another provider: a copy on the same machine or at the same provider disappears
  together with it.

## Cost

About 1,000 RUB per month for the VDS and backup storage — an estimate, prices not checked; one
or two evenings for the initial setup.
