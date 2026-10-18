#!/bin/sh
# Nightly copy of the database and the files on the instance itself, kept 7 days.
# A stopgap: decision 0013 wants encrypted copies at another provider.
set -eu
target=/var/backups/coloqo
install -d -m 0700 "$target"
stamp=$(date +%F)
runuser -u postgres -- pg_dump -Fc coloqo > "$target/coloqo-$stamp.dump.partial"
mv "$target/coloqo-$stamp.dump.partial" "$target/coloqo-$stamp.dump"
if [ -d /var/lib/private/coloqo/files ]; then
    tar -C /var/lib/private/coloqo -czf "$target/files-$stamp.tar.gz" files
fi
find "$target" -type f -mtime +7 -delete
