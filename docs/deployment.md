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
SMTP and automated backups with a full restore test still require setup.

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
temporary file. A lock prevents overlapping runs.

After success, completed `ttc-YYYY-MM-DD_HHMMSS-*.dump` files in this directory
older than 14 days are deleted. Never use this directory for long-term archives.
Progress and failures go to the terminal (or the journal when scheduled).
Scheduling a daily systemd timer is still pending; adding the script alone does
not create automatic backups or notifications.

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
