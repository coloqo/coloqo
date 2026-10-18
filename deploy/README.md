# Deploying the cloud instance

The cloud instance `app.coloqo.team` runs on one VDS without containers (decision 0016): the
server is a systemd service in a virtual environment, Caddy terminates TLS in front of it.

| File | On the server |
|---|---|
| `setup.sh` | first setup: Caddy, uv, Python 3.14, the service; safe to run again |
| `deploy.sh` | `/opt/coloqo/deploy.sh`: installs a release and switches to it |
| `coloqo.service` | `/etc/systemd/system/coloqo.service` |
| `Caddyfile` | `/etc/caddy/Caddyfile` |
| `backup.sh`, `coloqo-backup.service`, `coloqo-backup.timer` | the nightly copy |

Settings of the instance are in `/etc/coloqo/coloqo.env` (root only): `setup.sh` writes the
database address, the GitHub OAuth App is added by hand:

```
COLOQO_GITHUB_CLIENT_ID=...
COLOQO_GITHUB_CLIENT_SECRET=...
COLOQO_DATABASE_URL=postgresql+psycopg://coloqo:<password>@127.0.0.1:5432/coloqo
```

The OAuth App's callback is `https://app.coloqo.team/api/auth/github/callback`.

## First setup

1. VDS with Debian 13; a user with `sudo`.
2. DNS: an `A` record for `app.coloqo.team` pointing to the server (and `AAAA` if it has IPv6).
   Caddy obtains the certificate on start, so the record must point to the server first.
3. Copy this directory to the server and run `sudo sh setup.sh` there: Caddy, uv, Python 3.14,
   PostgreSQL with the `coloqo` role and database, the service and the backup timer.
4. Add the GitHub OAuth App to `/etc/coloqo/coloqo.env`.
5. Release and deploy, as below; the server migrates the database when it starts.

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

## Backups

Every night at 03:30 `backup.sh` dumps the database and packs the files into
`/var/backups/coloqo`, kept 7 days. Restore: `pg_restore -d coloqo --clean <dump>` as `postgres`
with the service stopped, and unpack the files into `/var/lib/private/coloqo/`.

## Not done yet

Encrypted copies at another provider and the external check of `/api/health` (decision 0013).
