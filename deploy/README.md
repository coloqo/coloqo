# Deploying the cloud instance

The cloud instance `app.coloqo.team` runs on one VDS without containers (decision 0016): the
server is a systemd service in a virtual environment, Caddy terminates TLS in front of it.

| File | On the server |
|---|---|
| `setup.sh` | first setup: Caddy, uv, Python 3.14, the service; safe to run again |
| `deploy.sh` | `/opt/coloqo/deploy.sh`: installs a release and switches to it |
| `coloqo.service` | `/etc/systemd/system/coloqo.service` |
| `Caddyfile` | `/etc/caddy/Caddyfile` |

## First setup

1. VDS with Debian 13; a user with `sudo`.
2. DNS: an `A` record for `app.coloqo.team` pointing to the server (and `AAAA` if it has IPv6).
   Caddy obtains the certificate on start, so the record must point to the server first.
3. Copy this directory to the server and run `sudo sh setup.sh` there.
4. Release and deploy, as below.

## Release

From a commit on `main` whose `server/pyproject.toml` has the new version:

```sh
git tag server-v0.1.0 && git push origin server-v0.1.0
```

The `Release server` workflow builds the web, puts it into the server wheel and attaches the
wheel, `requirements.txt` with hashes and `SHA256SUMS` to the GitHub Release `server-v0.1.0`.

## Deploy and roll back

```sh
ssh <server> sudo /opt/coloqo/deploy.sh 0.1.0
```

The script installs the release into `/opt/coloqo/releases/0.1.0`, points
`/opt/coloqo/current` to it, restarts the service and waits for `/api/health`. Deploying an
installed version again only switches to it — that is the rollback.

Logs: `journalctl -u coloqo` and `journalctl -u caddy`.

## Updates

- Debian and Caddy: `unattended-upgrades`, automatically.
- Python: `sudo env UV_PYTHON_INSTALL_DIR=/opt/coloqo/python uv python upgrade 3.14`, then
  `sudo systemctl restart coloqo`.
- uv: change `UV_VERSION` and `UV_SHA256` in `setup.sh` and run it again.

## Not done yet

PostgreSQL, nightly backups and the external check of `/api/health` (decision 0013) come with
the first stored data.
