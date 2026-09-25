# Development setup

## Prerequisites

- Git
- Docker with Docker Compose
- Conda
- Node.js and npm

The frontend declares npm 10.9.2 as its package manager version. The backend
environment currently targets Python 3.13.

## Start PostgreSQL

Run from the repository root:

```powershell
docker compose up -d db
```

The Compose service creates a local development database on
`127.0.0.1:5432`. The credentials in `compose.yaml` are development-only
credentials.

To inspect the service without changing data:

```powershell
docker compose ps
docker compose logs db
```

Be careful with `docker compose down -v`: the `-v` option removes the database
volume and its data.

## Configure the backend

Run the following commands from `backend/`:

```powershell
conda env create -f environment.yml
conda activate ttc-backend
Copy-Item .env.example .env
```

Adjust `.env` for the local database and replace `JWT_SECRET_KEY=CHANGE_ME`
with a local secret. Never commit `.env`.

Because imports use `app.*`, start backend tools with `backend/` as the current
working directory.

## Database migrations

The migration history starts with a complete schema baseline. After starting
PostgreSQL and configuring `backend/.env`, a new empty database can be built
entirely from the migration history with:

```powershell
alembic upgrade head
```

To verify that the migrated schema matches the current SQLModel metadata, run:

```powershell
alembic check
```

Generated revisions are drafts and must be reviewed before they are applied.
Schema migrations do not create default roles or the first administrator.
After migration, API startup automatically ensures ADMIN, EDITOR and
TEAM_REPORTER exist, preserving existing roles. Startup fails if this cannot
complete (for example, if migrations are missing). No administrator is created;
that remains a separate setup concern documented in [known-issues.md](known-issues.md).

Do not use `alembic stamp` as a repair command without first comparing the
actual schema with the target revision. `stamp` changes Alembic's recorded
revision but does not modify tables.

## First administrator

After migrations and the first API startup (which initializes default roles),
run from the project root:

```powershell
docker compose --env-file .env.production -f compose.prod.yaml build api
docker compose --env-file .env.production -f compose.prod.yaml run --rm api python -m scripts.users create-admin
```

Without Docker, run `python -m scripts.users create-admin` from `backend/` with
the backend environment active. The command writes a new active account and its
ADMIN assignment atomically. It prompts for name, email and a password of 12 to
128 characters twice, without echoing the password. An interactive terminal is
required; do not use `-T`, password arguments or piped input. No email is sent.
Existing accounts are not promoted or reset. An existing ADMIN account blocks
setup even when disabled; concurrent PostgreSQL calls serialize on the ADMIN row.
The command returns a nonzero exit status on failure and leaves no partial account.

## Start FastAPI

Media uploads use `MEDIA_DIRECTORY` (default `output/media`, relative to
`backend/`) and `MEDIA_MAX_UPLOAD_BYTES` (default 20971520). Use a persistent
directory or mounted volume in deployment. The directory is not publicly served.
`POST /api/admin/media/images` accepts a multipart `file` from authenticated
ADMIN, EDITOR or TEAM_REPORTER users. The response contains the new media ID;
`GET /api/admin/media/images/{id}` retrieves the WebP master for its uploader,
EDITOR or ADMIN using bearer authentication. Responses disable caching.
The article editor includes a reusable upload dialog and authenticated cover
preview. The selected media ID is associated when saving the article. Gallery
integration, existing-media selection and public image delivery remain planned.

From `backend/` with the Conda environment active:

```powershell
fastapi dev app/main.py
```

The API is then normally available at `http://localhost:8000`; interactive API
documentation is available at `http://localhost:8000/docs`.

## Logging

The backend writes application logs to the console. File logging is enabled by
default and writes size-rotated files below `backend/output/logs`:

- `application.log` contains application messages;
- `mytischtennis.log` additionally collects messages from
  `app.adapters.outbound.mytischtennis`, `app.core.competition.application`
  and their child loggers.

The following `.env` settings control logging:

```dotenv
LOG_LEVEL=INFO
MYTT_LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_DIRECTORY=output/logs
LOG_MAX_BYTES=5242880
LOG_BACKUP_COUNT=5
```

Relative log directories are resolved from `backend/`, independent of the
process working directory. Rotated files use suffixes such as `.1` and `.2`.
Do not log passwords, tokens, cookies, authorization headers, or complete API
responses containing unnecessary personal data. Player names and external
identifiers should be limited to `DEBUG` messages where possible.

Python's standard `RotatingFileHandler` is suitable for the current
single-process development setup. When running multiple Uvicorn workers or in
containers, prefer console logging with rotation handled by the runtime. A
shared file handler is not safe for concurrent rotation by multiple processes.

## Start Angular

Run from `frontend/`:

```powershell
npm install
npm start
```

Angular serves the application at `http://localhost:4200`. Requests below
`/api` are proxied to FastAPI during development.

## Checks

Frontend:

```powershell
npm test
npm run build
```

The article browser check uses Playwright with installed Microsoft Edge and a
mocked API. Start Angular on port 4201, then run from `frontend/`:

```powershell
node scripts/check-articles.cjs
```

Set `ARTICLE_TEST_URL` to use another local preview URL, and `BROWSER_CHANNEL`
to use another installed Playwright browser channel. The check exercises reporter,
editor and member views, direct editorial actions, and responsive layouts with
Axe WCAG AA checks. Screenshots are written to ignored `frontend/tmp/article-checks`.
It does not modify application data. Google Fonts requires network access during
the production build.

Backend tests use `pytest` as the common runner. It discovers both the existing
`unittest.TestCase` tests and the pytest functions in nested directories.
`test_backend_architecture.py` checks every core module for forbidden
infrastructure imports, including relative imports.
Activate `ttc-backend` and run from `backend/`:

```powershell
python -m pytest
```

`pytest` is included in `backend/environment.yml`. For an existing environment,
install the added test dependency with `python -m pip install pytest`.
`pytest.ini` sets the test directory and Python import root. `tests/conftest.py`
sets test-only database/signing settings before imports; tests use in-memory
SQLite databases and mocked external clients, not the local PostgreSQL data.
Do not use `unittest discover` as the full-suite command: it misses pytest functions.

The suite covers Events, article draft creation, Users/Auth (roles, cookies,
token rotation, revocation, rollback, and core dependency boundaries), and
competition imports (including historical batches and CLI entry points), but
is not yet a complete backend test suite.
Scripts that contact
myTischtennis or write to PostgreSQL are integration utilities, not isolated
unit tests. Inspect their arguments and effects before running them.

### Optional PostgreSQL outbox checks

The article CMS additionally requires migration `c9e15f30a624`. Its tests in
`tests/test_article_cms_postgres.py` use the same disposable-database fixture and
`TTC_TEST_POSTGRES_URL` below, covering schema upgrades and concurrent claims.
The application database is never used by these tests.

Set `TTC_TEST_POSTGRES_URL` to a PostgreSQL administrative connection URL
(SQLAlchemy format, `postgresql+psycopg://.../postgres`) with CREATEDB permission,
then run `python -m pytest tests/test_outbox_postgres.py` from `backend/`.
These tests create and drop only randomly named `ttc_outbox_test_*` databases;
they never migrate the application database. They cover clean migration,
upgrade with existing data, schema comparison, and concurrent detail imports.
Without that variable, these tests are skipped by the normal suite.

## Content worker

After `alembic upgrade head`, run `python -m scripts.content worker` from `backend/`
to start periodic current-game synchronization and outbox processing. This performs
real imports and creates article drafts. The worker is a separate process and
must be started explicitly; FastAPI does not launch it. See
[Content automation](content-automation.md) for intervals, manual reports,
draft editing, message status and retry commands.

The worker now uses database-backed nightly and match-relative scheduling.
Migration `a7c93d1e8402` is required. Use `python -m scripts.content sync-status`
to inspect it and `python -m scripts.content request-sync` to request a general
sync. `worker --once` performs at most one due job, rather than forcing a full
sync. See [MyTT automation](mytt-automation.md) for ADMIN API contracts and defaults.

Manual per-match detail reloads and the grouped ADMIN match overview additionally
require migration `b8d04e2f9513`. Tests in `test_match_reload*.py` cover the HTTP
contract, sorting, durable requests, recovery and report suppression. PostgreSQL
checks use the same disposable-database fixture and `TTC_TEST_POSTGRES_URL` as the
outbox tests; they cover upgrades, cascading job deletion, concurrent requests and
competing workers without contacting myTischtennis.

## Benutzer-CMS und E-Mail-Versand

Die Benutzerverwaltung benötigt Migration `d4f26a41b735`. `alembic upgrade head`
ergänzt die Passwort-Link-Tabelle und einen nullable Zeitstempel zur Invalidierung
von Sitzungen; bestehende Konten und Mitgliedsdaten bleiben erhalten.

In der lokalen, nicht versionierten `backend/.env` werden für den Versand
folgende Werte benötigt (siehe `.env.example`):

```dotenv
PUBLIC_FRONTEND_URL=http://localhost:4200
PASSWORD_LINK_MINUTES=60
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_USERNAME=YOUR_USERNAME
SMTP_PASSWORD=YOUR_PASSWORD
SMTP_SENDER=verein@example.org
SMTP_STARTTLS=true
```

Für die veröffentlichte Anwendung muss `PUBLIC_FRONTEND_URL` die HTTPS-Adresse
der Website enthalten. Der Adapter verwendet SMTP mit STARTTLS; Zugangsdaten
werden nur genutzt, wenn ein Benutzername konfiguriert ist. Für einen separaten
lokalen Mail-Testserver kann STARTTLS deaktiviert werden. Kein Mailserver und
keine echten Versandzugangsdaten werden durch das Repository eingerichtet.
Nach Änderungen an den Einstellungen das Backend neu starten.

Ohne SMTP lässt sich ein Konto vollständig anlegen und bearbeiten. Das Formular
meldet dann, dass die Einladung nicht versendet wurde; alternativ kann die
Einladungsoption beim Anlegen deaktiviert werden. Der Benutzer kann sich erst
anmelden, nachdem er über einen zugestellten Link sein Passwort festgelegt hat.

Zusätzliche Prüfungen:

```powershell
# Im backend-Verzeichnis; PostgreSQL-Variable wie oben beschrieben
python -m pytest tests/test_user_administration.py tests/test_users_postgres.py
# Im frontend-Verzeichnis, mit Angular auf Port 4202
node scripts/check-users.cjs
```

Der Browsercheck arbeitet mit simulierten API-Antworten, versendet keine E-Mails
und verändert keine Konten. Er prüft Rollen, Sperren, Anlegen mit bestehendem
Mitglied, Einladungen, Suche, Löschen und Passwortfestlegung sowie WCAG-AA-Regeln
im Inhaltsbereich bei Desktop-/Mobilgrößen. Screenshots liegen unter dem
ignorierten `frontend/tmp/user-checks`. `USERS_TEST_URL` und `BROWSER_CHANNEL`
überschreiben Vorschauadresse und Browser (Standard: Microsoft Edge).

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to main, pull requests targeting main,
and manual workflow dispatch. Backend and frontend checks run independently;
Docker builds follow only after both pass. New runs cancel older runs on the
same branch or pull request. Jobs have read-only repository permissions and
do not use production secrets, contact the VPS, publish images or deploy.

- Backend: Python 3.13, both hash-locked requirements files, `pip check`,
  `alembic upgrade head` and `alembic check` against a fresh PostgreSQL 18 database,
  then the complete pytest suite.
- PostgreSQL integration tests receive TTC_TEST_POSTGRES_URL pointing to the
  temporary CI service. They create and drop their own disposable databases;
  they are not silently skipped for a missing connection setting. The CI-only
  user/password are public test credentials, not production credentials.
- Frontend: Node.js 22, npm 10.9.2, `npm ci`, Angular tests without watch mode,
  and the production build. Google Fonts inlining requires internet access.
- Docker: build the backend and frontend Dockerfiles independently, without push.

After committing and pushing the workflow, inspect the first run in GitHub's
Actions tab. Local validation does not replace that first hosted run. The custom
Playwright browser checks are not included yet. Branch protection / required
checks must be configured separately in GitHub; this file alone does not prevent
merging or pushing a failing change.

## Suggested learning workflow with Codex

Prefix a task with the kind of collaboration you want:

- `Erklaere:` for analysis without file changes;
- `Gemeinsam:` for small pair-programming steps;
- `Implementiere:` for a complete, bounded implementation followed by an
  explanation.

For database work, ask Codex to explain whether a command changes schema, data,
or only Alembic's recorded revision before executing it.
