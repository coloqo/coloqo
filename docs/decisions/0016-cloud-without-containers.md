# 0016. The cloud instance without containers

**Date:** 2026-10-18 · **Question:** A11 revisited, `docs/architecture/architecture.md` ·
**Refines:** decisions 0010, 0013

## Decision

- **No Docker on the cloud instance.** The server runs as a systemd service from a virtual
  environment; Caddy comes from its official apt repository; PostgreSQL, when it arrives, from
  Debian's packages. Replaces `docker compose` in decision 0013.
- **The web is built in CI.** A tag `server-v<version>` (on a commit in `main`) starts a workflow
  that builds the web, puts it inside the server wheel (`coloqo_server/static`) and attaches to a
  GitHub Release: the wheel, `requirements.txt` with hashes exported from `uv.lock`, and
  `SHA256SUMS`. The repository is public, so the server downloads them without a token.
- **Deployment is an explicit action:** `sudo /opt/coloqo/deploy.sh <version>` on the server.
  - Each version gets its own virtual environment in `/opt/coloqo/releases/<version>`:
    dependencies by hashes, then the wheel; `/opt/coloqo/current` is switched to it and the
    service restarted; the script waits for `/api/health`.
  - Rollback is deploying an installed version again: only the link is switched. The three
    newest releases besides the current one are kept.
- **Python 3.14 is installed by `uv`**: Debian 13 ships 3.13. Patch releases — `uv python
  upgrade 3.14`; virtual environments refer to the minor version, so they follow.
- **Isolation by systemd:** `DynamicUser`, `ProtectSystem=strict`, `NoNewPrivileges`, no
  capabilities; the server listens on `127.0.0.1:8000`, only Caddy is public.
- **Security updates of the system are automatic:** `unattended-upgrades` with Debian's
  security origin and Caddy's repository.
- **The container image stays** for the self-hosted edition (decisions 0009, 0011): CI builds
  it on every push to `main`; the cloud does not run it.
- The machine is set up by `deploy/setup.sh`, which can be run again; the restore test on a
  clean machine (decision 0013) starts with it.

## Why

- The VDS rented for the pilot has 1 vCPU and 1 GB of memory. Docker's daemons take about
  80–120 MB of it; Coloqo itself takes the same with or without them.
- Debian fixes Caddy, PostgreSQL and OpenSSL by itself; inside images nothing is fixed until
  someone pulls new images on their own schedule.
- Ports published by Docker bypass the host firewall through its own iptables rules: a
  PostgreSQL with `ports:` would be open to the internet.
- Building the web on the server would bring Node there and a memory peak of `npm ci` and
  `vite build` on 1 GB; CI builds it anyway.
- A release per tag, as for the plugin: the version on the server is named, a rollback is one
  command.

## Cost

- The cloud no longer runs the artifact that the self-hosted edition ships: errors of the image
  itself are not caught by our own use.
- Python on the server is updated with `uv`, not by Debian.
