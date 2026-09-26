#!/usr/bin/env bash
# Streamed over SSH by deploy.yml. Arguments: existing checkout, verified commit.
set -Eeuo pipefail
umask 077

# Read the entire block before running commands; none may consume the SSH script input.
{
phase=preflight
log() { printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
on_exit() {
    local status=$?
    if (( status != 0 )); then
        log "Deployment failed during: $phase. No automatic rollback was performed." >&2
        log 'If services were stopped, inspect the failure before restarting them or restoring data.' >&2
    fi
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

[[ $# == 2 && "$2" =~ ^[0-9a-f]{40}$ ]] || fail 'Expected checkout path and full commit SHA.'
project_dir=$1
target_sha=$2
cd -- "$project_dir"
[[ "$(git rev-parse --show-toplevel)" == "$PWD" ]] || fail 'Path must be the repository root.'
for executable in docker flock sudo systemctl curl python3; do
    command -v "$executable" >/dev/null
done
# Also excludes concurrent manual invocations; .git is never deployed or committed.
exec 9>"$(git rev-parse --git-path ttc-deploy.lock)"
flock -n 9 || fail 'Another deployment is already running.'
[[ -z "$(git status --porcelain)" ]] || fail 'Server checkout has local changes; resolve them first.'
[[ -f .env.production ]] || fail '.env.production is missing.'
docker info >/dev/null
sudo -n -l /usr/bin/systemctl start ttc-backup.service >/dev/null

phase=checkout
git fetch origin main
[[ "$(git rev-parse origin/main)" == "$target_sha" ]] || fail 'main has moved; start a new deployment after its CI succeeds.'
log "Previous checkout: $(git rev-parse HEAD); target: $target_sha"
# No reset --hard: tracked edits and untracked files are never discarded.
git checkout --detach "$target_sha"

compose=(docker compose --env-file .env.production -f compose.prod.yaml -f compose.server.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" exec -T db pg_isready --username=ttc --dbname=ttc

phase=build
"${compose[@]}" build api web
# Read only the public hostname, never print the full resolved Compose config.
site_address="$("${compose[@]}" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["web"]["environment"]["SITE_ADDRESS"])')"
[[ "$site_address" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || fail 'SITE_ADDRESS must be a bare hostname.'

phase=stop
"${compose[@]}" stop --timeout 30 api worker
phase=backup
# Synchronous start: a failing backup prevents the migration.
sudo -n /usr/bin/systemctl start ttc-backup.service
[[ "$(systemctl show ttc-backup.service --property=Result --value)" == success ]] || fail 'Backup service failed.'

phase=migration
"${compose[@]}" run --rm --no-deps -T api python -m alembic upgrade head
"${compose[@]}" run --rm --no-deps -T api python -m alembic check

phase=start
# Database and persistent volumes remain in place. Worker must be explicit.
"${compose[@]}" up -d --no-deps --no-build --force-recreate --wait --wait-timeout 120 api web worker

phase=verification
# Exercise HTTPS, Caddy routing, API and a database-backed public endpoint.
curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors \
    --resolve "$site_address:443:127.0.0.1" \
    --connect-timeout 5 --max-time 10 --output /dev/null "https://$site_address/"
curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors \
    --resolve "$site_address:443:127.0.0.1" \
    --connect-timeout 5 --max-time 10 "https://$site_address/api/event-categories" \
    | python3 -c 'import json,sys; data=json.load(sys.stdin); assert isinstance(data, list), "Expected API JSON list"'
"${compose[@]}" ps
log "Deployment completed: $target_sha"
} < /dev/null
