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

The intended command is:

```powershell
alembic upgrade head
```

However, the current migration history only works with the existing baseline
database. It cannot build the full schema from an empty database. Read
[known-issues.md](known-issues.md) before creating, stamping, downgrading, or
replacing a database.

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
  `app.integrations.mytischtennis` and its child loggers.

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

The backend currently has manually executable myTischtennis scripts but no
complete automated pytest suite. Scripts that contact myTischtennis or write to
PostgreSQL are integration utilities, not isolated unit tests. Inspect their
arguments and effects before running them.

## Suggested learning workflow with Codex

Prefix a task with the kind of collaboration you want:

- `Erklaere:` for analysis without file changes;
- `Gemeinsam:` for small pair-programming steps;
- `Implementiere:` for a complete, bounded implementation followed by an
  explanation.

For database work, ask Codex to explain whether a command changes schema, data,
or only Alembic's recorded revision before executing it.
