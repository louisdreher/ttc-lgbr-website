#!/usr/bin/env bash
# Run with sudo on the Linux server. Does not start/stop services or change DB data.
set -Eeuo pipefail
umask 077

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR=/var/backups/ttc-postgres
RETENTION_MINUTES=20160 # 14 days
partial_file=

log() { printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n "$partial_file" ]]; then
        rm -f -- "$partial_file"
    fi
    if (( status != 0 )); then
        log 'ERROR: Backup or retention cleanup failed; check preceding output.' >&2
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if (( EUID != 0 )); then
    printf 'Please run this script with sudo.\n' >&2
    exit 1
fi
for executable in docker flock mktemp find; do
    command -v "$executable" >/dev/null
done
[[ -f "$PROJECT_DIR/.env.production" ]]
[[ ! -L "$BACKUP_DIR" ]]
install -d -m 0700 -o root -g root "$BACKUP_DIR"

# Serialize manual and scheduled runs, including cleanup of old archives.
exec 9>"$BACKUP_DIR/.backup.lock"
if ! flock -n 9; then
    log 'Another backup is already running; skipping.'
    exit 0
fi

compose=(docker compose --project-directory "$PROJECT_DIR"
    --env-file "$PROJECT_DIR/.env.production"
    -f "$PROJECT_DIR/compose.prod.yaml"
    -f "$PROJECT_DIR/compose.server.yaml")

partial_file="$(mktemp "$BACKUP_DIR/.ttc-XXXXXXXX.dump.partial")"
log 'Starting PostgreSQL dump.'
# Redirection happens on the host. Credentials remain inside the db container.
"${compose[@]}" exec -T db pg_dump --username=ttc --dbname=ttc \
    --format=custom --no-owner --no-privileges > "$partial_file"
[[ -s "$partial_file" ]]

# This checks the archive table of contents, not a full database restoration.
"${compose[@]}" exec -T db pg_restore --list < "$partial_file" > /dev/null
backup_file="$BACKUP_DIR/ttc-$(date -u +'%Y-%m-%d_%H%M%S')-$$.dump"
mv -- "$partial_file" "$backup_file"
partial_file=
log "Backup created and archive listing checked: $backup_file"

# Only completed archives matching our own naming pattern are eligible.
# Preserve the current archive even if a host clock adjustment occurred.
find "$BACKUP_DIR" -maxdepth 1 -type f \
    -name 'ttc-????-??-??_??????-*.dump' ! -path "$backup_file" \
    -mmin "+$RETENTION_MINUTES" -print -delete
log 'Backup complete; retention cleanup finished.'
