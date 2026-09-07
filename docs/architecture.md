# Architecture

## Overview

The application is currently organized as a browser-based Angular frontend, a
FastAPI backend, and a PostgreSQL database.

Its product goal is to combine an attractive public club website with tools
that reduce recurring editorial and administrative work. Imported competition
data, club events, articles, and media are therefore modeled as connected
domains rather than unrelated pages. This foundation is intended to support
workflows such as automatically maintained calendars and future report
suggestions without giving up editorial control.

Planned automation includes generating editable draft reports through the
OpenAI API from structured event and competition data, as well as extracting
candidate calendar entries from PDF documents. Both workflows must keep a
human review and approval step before content is published or imported into
the authoritative event data.

```text
Browser
  |
  | HTTP /api
  v
Angular frontend
  |
  | development proxy
  v
FastAPI backend
  |
  | SQLModel / SQLAlchemy
  v
PostgreSQL

myTischtennis
  |
  | HTTP/JSON
  v
Synchronization services --> PostgreSQL
```

During development, Angular serves the application on port 4200 and proxies
`/api` requests to FastAPI on port 8000. PostgreSQL is exposed locally on
`127.0.0.1:5432` by Docker Compose.

## Frontend

The frontend is an Angular 21 standalone application. Its major areas are:

- public pages under the public layout;
- an authenticated internal area under `/intern`;
- a role-protected administration area under `/admin`;
- authentication state and HTTP behavior under `app/core/auth`.

Authentication state is held in Angular signals. The access token exists only
in memory. On application startup, the frontend attempts to obtain a new
access token through the refresh-token cookie and then loads the current user.

Several feature pages are currently placeholders. Route presence should not be
interpreted as a completed feature.

## Backend

The backend is split into technical infrastructure and domain-oriented code:

- `app/core`: settings and database access;
- `app/auth`: authentication, refresh sessions, and permission dependencies;
- `app/domains/users`: users and roles;
- `app/domains/members`: members and players;
- `app/domains/content`: events, articles, galleries, and media metadata;
- `app/domains/competition`: seasons, teams, matches, and league tables;
- `app/integrations/mytischtennis`: external API access and synchronization;
- `app/jobs`: planned scheduled synchronization.

`app.*` is the canonical Python import path. Backend commands therefore need
to run with `backend/` as the working directory, or otherwise make that package
root available explicitly.

The content domain is divided into `events`, `articles`, and `media`. `Event`
acts as the shared editorial context and calendar entry. It may reference a
`TeamMatch`, but the competition domain remains the owner of match data and
does not depend on content models. Articles and galleries may exist without an
event.

The event subdomain exposes an authenticated administrative API for listing,
creating, updating, and deleting events and for managing event categories.
`ADMIN` and `EDITOR` may use it. Bulk visibility changes and deletion of manual
events are supported. Fields synchronized from a linked team match are
protected from manual changes, while editorial fields remain editable.

The Angular administration area provides event filtering, selection, bulk
actions, and forms for creating and editing entries. The public event API only
returns public, non-match events in the requested date range. Its Angular page
offers list and calendar views as well as date and category filters. Team
matches are deliberately excluded from this public endpoint; their future
public presentation remains a separate concern.

The previous `app/domains/articles` model path remains as a compatibility
import. Its existing routers and schemas still require migration to the new
article model and should not yet be treated as a working CMS API.

## Backend architecture direction

The current backend structure grew incrementally and still mixes several
responsibilities in places. Some FastAPI routers receive SQLModel sessions
directly, application-style service functions construct SQLModel queries, and
domain and persistence models are often the same classes. This is the current
state, not the intended architecture for new components.

New backend functionality and code selected explicitly for refactoring should
move toward a component-oriented Ports and Adapters architecture. The first
component planned to use the structure is the article component. Existing
components remain in their current locations until they are migrated through
separate, reviewable changes.

The intended top-level responsibilities are:

```text
app/
  components/             application core, organized by domain component
    content/
      articles/
        application/      use cases, commands, queries, DTOs, and ports
        domain/           entities, value objects, domain services, and errors
  adapters/
    inbound/              FastAPI, CLI, and other driving adapters
    outbound/             persistence and external-service adapters
  platform/               settings, database setup, logging, and wiring support
```

This is a target structure. During the transition, the existing `app/core`,
`app/domains`, and `app/integrations` packages continue to be canonical for
code that has not been deliberately migrated. New code must not import a new
component through its internal modules merely to bridge the two structures;
such integration needs an explicit public contract.

The dependency direction is inward:

```text
inbound adapter --> application --> domain
                           |
                           v
                     output port
                           ^
                           |
outbound adapter -----------
```

Domain code is independent of FastAPI, Pydantic transport schemas, SQLModel,
SQLAlchemy, and concrete external services. Application code coordinates use
cases and depends on domain types and application-owned ports. Inbound
adapters translate HTTP, CLI, or other external input into application
commands and queries. Outbound adapters implement application-owned ports and
translate between application concepts and tools such as SQLModel,
PostgreSQL, or third-party APIs.

FastAPI's dependency system is part of the inbound adapter and composition
wiring. `Depends` may create request-scoped sessions, repositories, readers,
and use cases, but it must not appear in application or domain code. A
database session passed through dependency injection is still a concrete
infrastructure dependency; write use cases should instead depend on
repository or unit-of-work ports when they are migrated.

The backend will not introduce a command or query bus. Controllers call use
cases and query objects directly. Write operations may use immutable command
DTOs, domain objects, and repository ports. Read operations may use dedicated
reader ports and optimized result DTOs without reconstructing complete domain
objects. HTTP request and response schemas remain separate from
transport-independent application DTOs where that separation provides a
clear boundary.

Components should expose explicit public contracts and must not depend on the
internal implementation of another component. Direct calls are acceptable
when an immediate result is part of the same use case and the dependency is
represented by an intentional contract. Events are reserved for genuine
cross-component reactions; no event dispatcher or shared kernel should be
introduced without a concrete workflow that requires it.

See [ADR 0003](decisions/0003-component-oriented-backend.md) for the decision,
tradeoffs, and migration constraints.

## Authentication

Login combines two token types:

1. FastAPI validates email and password.
2. A short-lived JWT access token is returned in the response body.
3. A random refresh token is placed in an HttpOnly cookie.
4. Only a SHA-256 hash of the refresh token is stored in PostgreSQL.
5. The frontend sends the access token in the `Authorization` header.
6. On expiration, the refresh token is rotated and a new access token is
   issued.

Backend role dependencies remain the authoritative authorization layer.
Frontend guards control navigation but are not a security boundary.

The initial creation of roles and the first administrator is not yet solved.
See [known-issues.md](known-issues.md).

## Database and migrations

SQLModel defines the application tables and SQLAlchemy creates the PostgreSQL
engine. Alembic is intended to be the only mechanism for evolving the schema;
runtime table creation is disabled.

The migration chain contains a complete initial schema followed by migrations
for the content domain and later event and match metadata. It has been verified
against a new empty PostgreSQL database in the past. New migrations must
continue to be tested against both a new empty database and the intended
upgrade path.

## myTischtennis integration

The integration has two layers:

- `MyTischtennisClient` performs asynchronous HTTP requests;
- synchronization classes parse responses and persist schedules,
  registrations, meeting details, and league tables.

`CurrentSeasonSync` coordinates synchronization for the current half-season.
Separate scripts support historical imports. These imports are designed to be
run manually at present.

A scheduler is planned but has not been implemented or connected to the
FastAPI lifecycle.

## Planned content automation

The CMS is intended to assist editors rather than publish generated content
autonomously. A future drafting service may combine structured match or event
data with editorial guidance and use the OpenAI API to prepare article drafts.
Generated text must remain traceable, editable, and unpublished until an
authorized editor reviews it.

A separate planned import workflow will accept PDF documents containing club
dates or event schedules. It should extract proposed events, show the source
and any uncertain fields, detect possible duplicates, and require confirmation
before persisting data. The exact PDF extraction and validation architecture
has not yet been decided.
