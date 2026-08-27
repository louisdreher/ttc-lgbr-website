# Backend guidance

These instructions supplement the repository-level `AGENTS.md` for work in
the `backend/` directory.

## Python and FastAPI

- Use `app.*` as the canonical Python import path.
- Keep API routers thin and put reusable business logic in services or focused
  domain modules.
- Use FastAPI dependencies for database sessions, authentication, and
  authorization.
- Use explicit request and response schemas at API boundaries.
- Do not expose password hashes, token hashes, secrets, or internal session
  data in API responses or logs.
- Prefer structured logging over `print()` for application code.

## SQLModel and PostgreSQL

- Model required fields, nullability, uniqueness, indexes, and foreign keys
  intentionally.
- Explain relationship and delete behavior when adding or changing foreign
  keys.
- Keep transactions focused; related writes should succeed or fail together.
- Do not call `SQLModel.metadata.create_all()` as a substitute for Alembic
  migrations.

## Alembic

- Treat generated migrations as drafts and review them before applying them.
- Do not rewrite existing migration history without explicit approval.
- Do not use `alembic stamp` until the actual database schema has been checked
  against the target revision.
- Test migration changes on a new empty database as well as the intended
  upgrade path.
- Data migrations and schema migrations should make their intent explicit.

## Authentication

- Store passwords only as secure password hashes.
- Store refresh tokens only in hashed form.
- Keep authorization checks on the backend even when the frontend has guards.
- Do not add default credentials or hard-coded administrator passwords.

## myTischtennis integration

- Treat the external response format as untrusted input and validate required
  fields before writing to the database.
- Preserve idempotency where imports may run more than once.
- Avoid real external requests in automated unit tests; use fixtures or mocked
  HTTP responses.
- The scheduler is planned but not implemented. Do not describe the current
  job module as an active scheduler.
