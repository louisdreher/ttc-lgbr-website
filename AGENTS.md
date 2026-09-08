# Project guidance

## Project purpose

This is a learning project for Angular, FastAPI, PostgreSQL, SQLModel,
Alembic, Docker, and working with Codex.

## Collaboration style

- Explain important architectural and technical decisions.
- Distinguish clearly between analysis, recommendation, and implementation.
- Do not assume that every request authorizes implementation.
- Before larger changes, explain the intended design and affected files.
- Prefer small, reviewable changes.
- When the user wants to implement a part, provide guidance, examples, or a
  skeleton instead of completing the whole task.
- Point out alternatives and their tradeoffs without overengineering.
- Explain unfamiliar commands before using them when they may alter data.

Adapt to the collaboration mode requested by the user:

- `Erklaere`: Explain and analyze without modifying files.
- `Gemeinsam`: Work in small steps and leave selected implementation work to
  the user.
- `Implementiere`: Make the requested changes and explain the important parts
  afterward.

## Repository structure

- `frontend/`: Angular application
- `backend/`: FastAPI application and Alembic migrations
- `compose.yaml`: local PostgreSQL service
- `docs/`: architecture and development documentation

## General rules

- Never commit secrets or `.env` files.
- Preserve unrelated user changes.
- Do not rewrite migration history without explicit approval.
- Do not make destructive database changes without explaining the impact.
- Keep frontend and backend authorization rules consistent.
- Update documentation when an architectural decision changes.
- Mark planned functionality as planned instead of presenting it as complete.

## Backend architecture direction

New backend functionality and code that is deliberately refactored should
follow a component-oriented Ports and Adapters structure. Existing code may
still use the previous structure and must not be migrated incidentally as part
of an unrelated change.

The intended separation is:

- `app/core`: domain-oriented components containing application and
  domain code;
- `app/adapters/inbound`: delivery adapters such as FastAPI routers and CLI
  commands;
- `app/adapters/outbound`: implementations for persistence and external
  services;
- `app/bootstrap`: application-wide settings, logging, and composition.
  Database engine creation lives in
  `app/adapters/outbound/persistence/database.py`.

Dependency rules:

- Domain code must not depend on FastAPI, SQLModel, SQLAlchemy, Pydantic
  transport schemas, or concrete external services.
- Application code may depend on its domain model and its own ports, but not
  on inbound or outbound adapters.
- Inbound adapters may depend on application use cases. Outbound adapters
  implement ports defined by the application core.
- FastAPI `Depends` belongs in inbound adapters or composition and wiring
  code, not in domain or application code.
- HTTP request and response schemas belong to the HTTP adapter. Application
  commands, queries, and result DTOs must remain transport-independent.
- Controllers call use cases and query objects directly. Command and query
  buses are not planned.
- Write use cases should use domain objects and repository ports. Read use
  cases may use dedicated reader ports that return optimized DTOs.
- Cross-component communication must use an explicit public contract, port,
  or event. Do not import another component's internal implementation.
- Keep shared code minimal. Do not create a general-purpose shared utilities
  package.
- Introduce abstractions only for a concrete boundary or variation point, and
  keep architecture changes small and reviewable.

## Verification

- Frontend changes: run the relevant Angular tests and build.
- Backend changes: run the relevant backend tests when such tests exist.
- Migration changes: verify them against a new empty database.
- Report which checks were run and which were not.
