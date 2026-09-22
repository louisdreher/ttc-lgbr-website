# Backend guidance

These instructions supplement the repository-level `AGENTS.md` for work in
the `backend/` directory.

## Architecture entry points

Before changing backend architecture or adding a use case, read
[the architecture overview](../docs/architecture.md) and the relevant component
walkthrough. For Competition, read [Competition](../docs/competition-domain.md);
for sync changes also read [myTischtennis](../docs/mytischtennis-architecture.md).
Other walkthroughs: [Events](../docs/events-architecture.md),
[Articles](../docs/articles-architecture.md),
[Users/Auth](../docs/users-auth-architecture.md).
Use [development setup](../docs/development.md) for running checks.
These files preserve decisions across chats; do not rely on conversation history.
Check the actual code and preserve unrelated work when documentation differs.

## Use-case and boundary conventions

- Implement use cases as classes with constructor-injected ports and `execute()`.
- Put general writing use cases in `application/commands.py`, reading use cases
  in `application/queries.py`, and their input/output DTOs in `application/dto.py`.
  Commands describe writes; queries describe reads. No empty query DTO is needed
  for a parameterless operation. Prefer frozen dataclasses for DTOs.
- Keep ports in `application/ports.py` and application errors in `errors.py`.
  Domain rules and errors belong to the domain. A component is an organizational
  boundary, not automatically an aggregate. Aggregate roots enforce their rules.
- Writes use domain objects and repository/unit-of-work ports; repositories do
  not commit. Reads use reader ports and result DTOs and need no write unit of work.
- Domain code must not import application code or import DTOs. Translate source
  DTOs in the application; translate provider-specific JSON in outbound adapters.
- Keep HTTP schemas separate from core DTOs. Routers validate transport input,
  call use cases, and translate application errors to HTTP status codes.
  HTTP `dependencies.py` delegates construction to bootstrap; `Depends` and
  authorization remain outside the core. Bootstrap chooses concrete adapters.
- Preserve the Competition split: general code directly in `application/`, all
  sync code in `application/sync/` (commands, batches, backfill, queries, mapping,
  DTOs, imports, ports, errors). Do not restore the former `application/usecases/`
  layout or `domain/imports.py`.
- Competition's general and sync areas own separate reader, repository, and
  unit-of-work contracts. A concrete SQL adapter may implement both contracts;
  this does not require duplicate adapters. General application code must not
  depend on sync-specific contracts.
- Use `bootstrap/competition.py` for general composition and
  `bootstrap/competition_sync.py` for sync composition.
- Current Competition GET routes live under `/api/competition`. Internal team
  lineup requires ADMIN; other implemented reads are public. Preserve these
  permissions unless the user requests a change. Candidate reads and assignment
  PUT/DELETE routes also require ADMIN; see competition-domain.md for the simple
  registration eligibility rule. Scheduled sync runs through the separate content worker.
  Never trigger sync from a read query.
- MyTischtennis automation has ADMIN-only endpoints under `/api/admin/mytt`.
  Settings and latest status live in the database; HTTP requests only enqueue
  a coalesced general sync. See `docs/mytt-automation.md`. Keep scheduled jobs
  behind the PostgreSQL worker lock, and keep heartbeat/outbox independent.
- Keep changes scoped: these conventions guide new work, not incidental bulk
  migration of unrelated components. Update walkthroughs when decisions change.

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
- The content worker runs scheduled sync and outbox processing when explicitly
  started with `python -m scripts.content worker`; FastAPI does not start it.
- Generated reports remain drafts. Preserve generation provenance and idempotency
  when editing articles or extending message handlers. See `docs/content-automation.md`.
