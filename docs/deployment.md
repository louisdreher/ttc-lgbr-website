# Manual deployment preparation

`compose.prod.yaml` runs the built application locally, with web on
127.0.0.1:8080 and API on 127.0.0.1:8000. For the public server, additionally
load `compose.server.yaml` (Docker Compose 2.24.4 or newer). It removes the API
host port, replaces web ports with TCP 80/443, enables secure refresh cookies,
and sets the public frontend URL. PostgreSQL has no published port.

The server's untracked `.env.production` must contain DATABASE_URL,
POSTGRES_PASSWORD, JWT_SECRET_KEY and a bare hostname:

```dotenv
SITE_ADDRESS=neu.ttclangenbrombach.de
```

Do not include a URL scheme or path in SITE_ADDRESS. Caddy uses this hostname
for automatic HTTPS; DNS must point to the server and TCP 80/443 must be
reachable. The caddy_data volume preserves certificates and private keys;
caddy_config preserves Caddy runtime configuration. These volumes are not backups.

Validate without printing secrets (from the project root):

```sh
sudo docker compose --env-file .env.production -f compose.prod.yaml -f compose.server.yaml config --quiet
```

Always include both files, in that order, for server operations. Existing
images must be rebuilt after Dockerfile, application or Caddyfile changes.
Migrations must run before starting the API or worker. API startup initializes
roles; the first administrator is created explicitly (see development.md).
Member/competition data can be transferred separately. After a data-only import
of team matches, run `python -m scripts.maintenance.backfill_team_match_events`
in an API one-off container to create the associated events and category.
SMTP remains a separate setup step. Database backups are described below.

## PostgreSQL dumps

Run `sudo bash scripts/backup-postgres.sh` from the server checkout. The script
resolves the project directory from its own location and reads the server's
`.env.production` through Compose. PostgreSQL must already be running.
It creates a full custom-format dump (data and schema, without ownership or
privilege restoration commands) of database `ttc`. No services are stopped.

Dumps are stored in `/var/backups/ttc-postgres`, owned by root with directory
mode 0700 and file mode 0600. Filenames contain a UTC timestamp and process ID.
The archive is first written to a temporary file and its table of contents is
checked with `pg_restore --list` before being renamed to a completed `.dump`.
This is not a full restoration test. A failed dump/check removes only its
temporary file. A lock prevents overlapping runs; the script waits up to five
minutes for it and fails on timeout rather than reporting a skipped backup as success.

After success, completed `ttc-YYYY-MM-DD_HHMMSS-*.dump` files in this directory
older than 14 days are deleted. Never use this directory for long-term archives.
Progress and failures go to the terminal (or the journal when scheduled).
The Contabo server has a daily `ttc-backup.timer` and a one-shot
`ttc-backup.service`, and a downloaded dump has been restored in a separate local
test database. These units were configured manually: adding this script to a new
server alone does not create automatic backups or notifications. The service must
run as root with `Type=oneshot`, without `RemainAfterExit`, and execute
`/bin/bash /home/deploy/ttc-lgbr-website/scripts/backup-postgres.sh`.

These dumps contain member data and password hashes. They are not encrypted,
do not contain media files or server secrets, and remain on the same server.
Periodically download a copy to protected local storage. Access as `deploy`
requires an explicit sudo-assisted copy to a private transfer directory; do not
make the root backup directory public for SCP. Test restoration in a separate
database, never by overwriting production as a test.

## Background worker

The worker uses the same backend image as the API but runs
`python -m scripts.content worker`. It needs PostgreSQL and has no published
ports or media mount. JWT_SECRET_KEY is supplied because the shared settings
require it. Scheduling lives in the database, not in environment variables.

The `automation` profile keeps a plain local `up -d` from starting imports
unexpectedly. Explicitly targeting the service starts it without a profile flag:

```sh
sudo docker compose --env-file .env.production -f compose.prod.yaml -f compose.server.yaml run --rm api python -m scripts.content sync-status
sudo docker compose --env-file .env.production -f compose.prod.yaml -f compose.server.yaml up -d worker
sudo docker compose --env-file .env.production -f compose.prod.yaml -f compose.server.yaml logs --tail 80 worker
```

Starting the worker performs real myTT imports when due and processes outbox
messages. The latest overdue nightly run can be caught up immediately. New
current results can create article drafts, never automatically published articles.
It does not reimport all historical details. Check sync-status / the admin myTT
view for a fresh heartbeat and completed/failed runs; a running container alone
does not prove imports succeeded. See mytt-automation.md for scheduling semantics.

Stop with the same Compose options followed by `stop worker`. A started worker
restarts after host reboots unless explicitly stopped. When deploying a new
backend image, recreate both `api` and `worker`; the running worker does not
automatically switch to a rebuilt image. Include `--profile automation` when
operating on the entire stack with the worker enabled.

## Manual GitHub deployment

`.github/workflows/deploy.yml` provides **Actions > Deploy > Run workflow**.
Select `main`, after the CI run for its current commit succeeds. A push only
starts CI; it never deploys automatically. The workflow requires a successful
latest push-CI run for the exact selected SHA and rejects other branches. If CI
is still running, start Deploy again after it succeeds. If `main` advances before
the server fetch, the deployment aborts rather than substituting an untested commit.

In GitHub, configure the `production` environment to allow only branch `main`:

| Setting | Type | Value |
| --- | --- | --- |
| DEPLOY_HOST | Variable | 194.163.154.138 |
| DEPLOY_USER | Variable | deploy |
| DEPLOY_PATH | Variable | /home/deploy/ttc-lgbr-website |
| DEPLOY_SSH_KEY | Secret | Dedicated private SSH key for Actions |
| DEPLOY_KNOWN_HOSTS | Secret | Verified `IP ssh-ed25519 public-key` line |

Install the corresponding public key in the server user's `authorized_keys`.
Obtain the host key through the existing trusted server connection, not by
blindly accepting an SSH scan during deployment. The workflow enforces host-key
verification. The server `.env.production` stays on the server.

The `deploy` user must be in the Docker group (effectively root-level access).
The manually configured sudoers rule permits only the backup service command
without a password:

```sudoers
deploy ALL=(root) NOPASSWD: /usr/bin/systemctl start ttc-backup.service
```

The runner streams `scripts/deploy.sh` from the selected commit over SSH, so no
manual initial script installation is needed. The server checkout must be clean;
ignored files such as `.env.production` are preserved. The script fetches `main`
and checks out the verified SHA in detached-HEAD mode. Future deployments use
the same procedure; do not use `git pull` in this detached checkout.

Deployment builds API/web images while the old containers still run, stops API
and worker, waits for the backup service, migrates and checks the schema, then
recreates API/web/worker. PostgreSQL and volumes are not recreated. HTTPS checks
cover the frontend and `/api/event-categories` (including a database query).
The worker is explicitly started, but its import results/heartbeat still need
checking in the admin view; a running container is not proof of a completed import.
Images are rebuilt on the server from the checked source; this does not promote
the exact image bytes built in CI, and base image tags can change.

GitHub serializes deployments without cancelling the active one; a server lock
also rejects overlapping manual invocations. Avoid simultaneous manual Compose
operations. There is a short interruption from stopping writers through successful
startup. Do not cancel a running deployment during this period.

On failure the job is red and reports the phase. Build failures leave the old
containers running. Failures after stopping services can leave the API/worker
stopped; startup/verification failures may leave the new services running.
There is deliberately no automatic database downgrade or backup restore.
Inspect the Actions log and server service state before recovery. A checkout SHA
alone is not enough for rollback when database migrations have been applied.
No volume deletion or Docker image pruning is part of deployment.

The first real deployment must still be verified on the server after this
workflow is committed and pushed. Local syntax/control-flow checks do not test
the SSH credentials, sudoers rule or production environment.
