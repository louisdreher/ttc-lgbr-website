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
Schema migrations also do not create application bootstrap data such as roles
or the first administrator; that remains a separate setup concern documented
in [known-issues.md](known-issues.md).

Do not use `alembic stamp` as a repair command without first comparing the
actual schema with the target revision. `stamp` changes Alembic's recorded
revision but does not modify tables.

## Start FastAPI

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

## Suggested learning workflow with Codex

Prefix a task with the kind of collaboration you want:

- `Erklaere:` for analysis without file changes;
- `Gemeinsam:` for small pair-programming steps;
- `Implementiere:` for a complete, bounded implementation followed by an
  explanation.

For database work, ask Codex to explain whether a command changes schema, data,
or only Alembic's recorded revision before executing it.
