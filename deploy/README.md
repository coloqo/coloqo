# Deploying the cloud instance

The cloud instance `app.coloqo.team` is one VDS running `docker compose`: Coloqo and Caddy
(decision 0013). GitHub Actions builds the image on every push to `main` and pushes it to GHCR
as `ghcr.io/coloqo/coloqo:latest` and `:sha-<commit>`.

## First server setup

1. VDS: Ubuntu 24.04, 2 vCPU, 4 GB. Docker from Docker's official repository (`docker-ce`
   with `docker-compose-plugin`).
2. DNS: an `A` record for `app.coloqo.team` pointing to the server (and `AAAA` if it has
   IPv6). Caddy obtains the certificate on the first request, so the record must point to the
   server before the start.
3. Firewall: inbound 22/tcp, 80/tcp, 443/tcp, 443/udp (HTTP/3).
4. Image access: if the GHCR package is public, nothing is needed; if private,
   `docker login ghcr.io` with a GitHub token that has `read:packages`.
5. Files:

   ```sh
   sudo mkdir -p /opt/coloqo && cd /opt/coloqo
   # copy compose.yaml and Caddyfile from this directory here
   cp .env.example .env   # adjust if needed
   docker compose pull && docker compose up -d
   ```

6. Check: `curl https://app.coloqo.team/api/health` → `{"status":"ok"}`.

## Update

```sh
cd /opt/coloqo && docker compose pull && docker compose up -d
```

Rollback: set `COLOQO_IMAGE=ghcr.io/coloqo/coloqo:sha-<commit>` in `.env` and run the same
command.

## Trying it locally

From the repository root:

```sh
docker build -t coloqo:dev .
cd deploy && COLOQO_DOMAIN=localhost COLOQO_IMAGE=coloqo:dev docker compose -p coloqo-local up -d
curl -k https://localhost/api/health
docker compose -p coloqo-local down -v
```

On `localhost` Caddy issues a certificate from its own CA, hence `-k`.

## Not done yet

PostgreSQL, nightly backups and the external check of `/api/health` (decision 0013) come with
the first stored data.
