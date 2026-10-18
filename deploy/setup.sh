#!/bin/sh
# First setup of the cloud instance (decision 0016), run as root from a copy of deploy/:
#   sudo sh setup.sh
# Safe to run again: it brings the machine to the same state.
set -eu
cd "$(dirname "$0")"

UV_VERSION=0.13.1
UV_SHA256=eadd9d27c134ab5ac1ffd4473b97a741407f3ea238288f03121fc4deddf90220

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg debian-keyring debian-archive-keyring \
    apt-transport-https unattended-upgrades postgresql >/dev/null

# PostgreSQL from Debian (decision 0016): a role and a database for Coloqo; the server
# connects over 127.0.0.1 with a password kept in /etc/coloqo/coloqo.env.
install -d -m 0755 /etc/coloqo
touch /etc/coloqo/coloqo.env
chmod 600 /etc/coloqo/coloqo.env
if ! grep -q '^COLOQO_DATABASE_URL=' /etc/coloqo/coloqo.env; then
    password=$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)
    if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'coloqo'" | grep -q 1; then
        runuser -u postgres -- psql -q -c "ALTER ROLE coloqo PASSWORD '$password'"
    else
        runuser -u postgres -- psql -q -c "CREATE ROLE coloqo LOGIN PASSWORD '$password'"
    fi
    echo "COLOQO_DATABASE_URL=postgresql+psycopg://coloqo:$password@127.0.0.1:5432/coloqo" \
        >> /etc/coloqo/coloqo.env
fi
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'coloqo'" | grep -q 1; then
    runuser -u postgres -- createdb -O coloqo coloqo
fi

# Caddy from its official repository; unattended-upgrades updates it with Debian's
# security fixes.
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
    | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
    > /etc/apt/sources.list.d/caddy-stable.list
cat > /etc/apt/apt.conf.d/52unattended-upgrades-caddy <<'CONF'
Unattended-Upgrade::Origins-Pattern { "origin=cloudsmith/caddy/stable"; };
CONF
apt-get update -qq
apt-get install -y -qq caddy >/dev/null

# uv, pinned and checked; it installs Python 3.14, which Debian 13 does not ship.
if [ "$(uv --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
    work=$(mktemp -d)
    curl -fsSL -o "$work/uv.tar.gz" \
        "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz"
    echo "$UV_SHA256  $work/uv.tar.gz" | sha256sum --check --quiet
    tar -xzf "$work/uv.tar.gz" -C "$work"
    install -m 0755 "$work"/uv-x86_64-unknown-linux-gnu/uv "$work"/uv-x86_64-unknown-linux-gnu/uvx \
        /usr/local/bin/
    rm -rf "$work"
fi

install -d -m 0755 /opt/coloqo /opt/coloqo/releases
UV_PYTHON_INSTALL_DIR=/opt/coloqo/python uv python install --quiet 3.14

install -m 0755 deploy.sh /opt/coloqo/deploy.sh
install -m 0755 backup.sh /opt/coloqo/backup.sh
install -m 0644 coloqo.service /etc/systemd/system/coloqo.service
install -m 0644 coloqo-backup.service /etc/systemd/system/coloqo-backup.service
install -m 0644 coloqo-backup.timer /etc/systemd/system/coloqo-backup.timer
install -m 0644 Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --quiet coloqo
systemctl enable --quiet --now coloqo-backup.timer
systemctl reload-or-restart caddy

echo "Set up. Deploy a release: sudo /opt/coloqo/deploy.sh <version>"
