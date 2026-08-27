# TTC Langen-Brombach Website

This repository contains the developing website and internal administration
tools for TTC Langen-Brombach. It is also a learning project for Angular,
FastAPI, PostgreSQL, SQLModel, Alembic, Docker, and collaboration with Codex.

## Project status

The project is under active development. The current foundation includes:

- an Angular frontend with public, internal, and administration layouts;
- a FastAPI backend with authentication, user roles, and initial article APIs;
- a PostgreSQL data model for members, teams, matches, and league tables;
- a myTischtennis client and synchronization code;
- Alembic migrations for an existing development database.

Several screens and APIs are still placeholders. The myTischtennis scheduler
and article workflow are not yet fully implemented. Known technical issues are
tracked in [docs/known-issues.md](docs/known-issues.md).

## Repository structure

```text
.
|-- frontend/       Angular application
|-- backend/        FastAPI application, SQLModel models, and Alembic
|-- docs/           Architecture and development documentation
`-- compose.yaml    Local PostgreSQL service
```

## Getting started

The detailed development setup is documented in
[docs/development.md](docs/development.md).

In short, local development consists of:

1. starting PostgreSQL with Docker Compose;
2. creating and activating the backend Conda environment;
3. configuring `backend/.env` from `backend/.env.example`;
4. applying the appropriate database migrations;
5. starting FastAPI from `backend/`;
6. installing and starting Angular from `frontend/`.

Do not use the migration instructions on an empty database yet. The existing
Alembic baseline does not create the complete initial schema. See the known
issues before changing or recreating the database.

## Documentation

- [Architecture](docs/architecture.md)
- [Development setup](docs/development.md)
- [Data model](docs/data-model.md)
- [Known issues](docs/known-issues.md)
- [Architecture decisions](docs/decisions/README.md)

