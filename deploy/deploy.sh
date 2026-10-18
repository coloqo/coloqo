#!/bin/sh
# Deploy a server release on the cloud instance: sudo /opt/coloqo/deploy.sh <version>
#
# Installs the release attached to the tag server-v<version> into its own virtual
# environment, points /opt/coloqo/current to it and restarts the service. Deploying an
# installed version again only switches to it: that is the rollback.
set -eu

version=${1:-}
if ! printf '%s\n' "$version" | grep -Eqx '[0-9]+\.[0-9]+\.[0-9]+'; then
    echo "usage: $0 <version>, e.g. $0 0.1.0" >&2
    exit 2
fi

root=/opt/coloqo
release=$root/releases/$version
base=https://github.com/coloqo/coloqo/releases/download/server-v$version
wheel=coloqo_server-$version-py3-none-any.whl
export UV_PYTHON_INSTALL_DIR=$root/python

if [ ! -x "$release/bin/python" ]; then
    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT
    for file in SHA256SUMS requirements.txt "$wheel"; do
        curl -fsSL --retry 3 -o "$work/$file" "$base/$file"
    done
    (cd "$work" && sha256sum --check --quiet SHA256SUMS)

    rm -rf "$release.partial"
    uv venv --quiet --python 3.14 "$release.partial"
    # Dependencies pinned by the lock file, with hashes; then the server itself.
    uv pip sync --quiet --python "$release.partial/bin/python" --require-hashes \
        --compile-bytecode "$work/requirements.txt"
    uv pip install --quiet --python "$release.partial/bin/python" --no-deps \
        --compile-bytecode "$work/$wheel"
    # The environment is used under its final path only: scripts in it are not relocatable,
    # and the service runs python -m, which is.
    mv "$release.partial" "$release"
fi

ln -sfn "$release" "$root/current.new"
mv -T "$root/current.new" "$root/current"
systemctl restart coloqo

for _ in $(seq 30); do
    if curl -fs -o /dev/null http://127.0.0.1:8000/api/health; then
        echo "Coloqo $version is up"
        # Keep the three newest releases besides the current one.
        ls -1t "$root/releases" | grep -vx "$version" | tail -n +4 \
            | while read -r old; do rm -rf "${root:?}/releases/$old"; done
        exit 0
    fi
    sleep 1
done
echo "Coloqo $version did not answer /api/health; roll back with: $0 <previous version>" >&2
journalctl -u coloqo -n 30 --no-pager >&2
exit 1
