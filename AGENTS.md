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

## Verification

- Frontend changes: run the relevant Angular tests and build.
- Backend changes: run the relevant backend tests when such tests exist.
- Migration changes: verify them against a new empty database.
- Report which checks were run and which were not.

