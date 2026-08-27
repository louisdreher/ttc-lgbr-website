# Known issues and deferred work

This document records known limitations that are intentionally not solved yet.
They should not be interpreted as accidental omissions or completed features.

## Alembic baseline cannot create a fresh database

### Status

Open; deferred.

### Current situation

The first Alembic revision is an empty baseline for a database whose tables
already existed. Later revisions alter those existing tables. As a result,
running `alembic upgrade head` against an empty PostgreSQL database does not
create the original tables and will fail when a later revision tries to alter
one of them.

### Impact

- A completely fresh database is not reproducible from migrations alone.
- Automated migration testing against an empty database is not yet possible.
- New development environments depend on the existing database state or a
  separate schema source.

### Intended future discussion

Because this is currently a single-developer learning project without a
published production migration history, one likely option is to replace the
current chain with a reviewed full-schema baseline. Before doing so, the
existing database must be backed up and its schema compared with the generated
baseline. No migration history should be rewritten until that work is
explicitly requested.

## No bootstrap process for roles and first administrator

### Status

Open; deferred.

### Current situation

User creation is protected by the `ADMIN` role. A new installation initially
has neither an administrator nor a guaranteed process that creates the default
roles. This creates a bootstrap cycle: an administrator is required to create
the first administrator.

### Impact

- A fresh installation cannot be initialized through the normal protected API.
- Manual database changes may currently be required.
- Role existence depends on prior database state.

### Intended future discussion

A future setup mechanism should create missing roles idempotently and provide a
safe, explicit way to create the first administrator. A dedicated CLI command
is a likely option. It must not introduce hard-coded credentials, default
passwords, or a publicly exposed bootstrap endpoint.

## Scheduler not implemented

### Status

Planned.

The myTischtennis synchronization can currently be run through scripts and
orchestration code. Scheduled execution has not been integrated into the
FastAPI application lifecycle and should not yet be relied upon.

## Article workflow incomplete

### Status

Planned.

The article model, public reads, and preliminary administration routes exist,
but the complete creation, publication, validation, and frontend workflow has
not been implemented.

