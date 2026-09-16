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

- `app/bootstrap`: settings, logging, and use-case composition;
- `app/adapters/outbound/persistence`: database setup and migrated persistence adapters;
- `app/adapters/inbound`: HTTP and CLI adapters;
- `app/adapters/outbound/competition`: the match-to-event bridge;
- `app/core/auth`: framework-free authentication use cases and refresh sessions;
- `app/core/users`: users and roles;
- `app/adapters/outbound/persistence/members`: member/player storage and imported-player adapter;
- `app/core/content`: event and article application/domain code;
- `app/adapters/outbound/persistence/media`: media and gallery storage;
- `app/core/competition`: seasons, teams, matches, and league tables;
- `app/adapters/outbound/mytischtennis`: external API access and response mapping;
- `app/core/competition/application`: general reads and internal lineup commands;
- `app/core/competition/application/sync`: current/historical imports and backfill;

Scheduled synchronization is implemented in a separate content worker, started
with `python -m scripts.content worker`. FastAPI does not start it automatically.

`app.*` is the canonical Python import path. Backend commands therefore need
to run with `backend/` as the working directory, or otherwise make that package
root available explicitly.

Content concerns include events, articles, and media; media currently has
persistence models without standalone core workflows. `Event`
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
frontend presentation remains a separate concern. Competition has its own
public reading API for schedules and match details.

The article draft-creation workflow uses a framework-free domain, a
`CreateArticle.execute(command)` use case, repository/unit-of-work ports,
HTTP and SQL adapters, and `app/bootstrap/articles.py` composition.
Persistence models live under `app/adapters/outbound/persistence/articles`.
Backend match-report generation and draft editing are implemented; publication,
public reads, and the frontend CMS workflow remain planned.
See [the article architecture walkthrough](articles-architecture.md).

## Backend architecture direction

The existing backend workflows now use component-oriented Ports and Adapters.
All SQLModel tables reside in outbound persistence adapters. The core is free
of framework and infrastructure imports; a project-wide test enforces this
boundary. Members and Media currently contain persistence structures rather
than standalone management workflows. Their future use cases remain planned.

New backend functionality and code selected explicitly for refactoring should
move toward a component-oriented Ports and Adapters architecture. Events now
uses this structure for CRUD, categories, queries, bulk actions, and match
synchronization. Articles follows the same architecture for its existing
draft-creation workflow. Users and Auth now follow this structure as well,
including password/JWT adapters and HTTP permission dependencies outside the core.
See [the Users/Auth walkthrough](users-auth-architecture.md). Competition reads, internal lineup commands, and imports
also use application classes and ports. Members and Media persistence models
have been moved without introducing unused application layers.

The intended top-level responsibilities are:

```text
app/
  core/                   application core, organized by domain component
    content/
      events/
        application/      use cases, commands, queries, DTOs, and ports
        domain/           entities, value objects, domain services, and errors
  adapters/
    inbound/              FastAPI, CLI, and other driving adapters
    outbound/             persistence and external-service adapters
  bootstrap/              settings, logging, and wiring support
```

This structure is implemented for Competition, Events, article draft creation, Users, and Auth. Database setup is located in
`app/adapters/outbound/persistence/database.py`. Competition tables live in
`persistence/competition`, member tables in `persistence/members`, and media
and gallery tables in `persistence/media`. New cross-component interactions
must use explicit public contracts, ports, or events.

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
transport-independent application DTOs.

Components should expose explicit public contracts and must not depend on the
internal implementation of another component. Direct calls are acceptable
when an immediate result is part of the same use case and the dependency is
represented by an intentional contract. Events are reserved for genuine
cross-component reactions; no event dispatcher or shared kernel should be
introduced without a concrete workflow that requires it.

Competition now stages `TeamMatchResultsImported` in a transactional outbox on
the first successful detail import. The message and results share one database
transaction; the SQL outbox lives in `adapters/outbound/persistence/messaging`,
separate from calendar Events. Message delivery uses expiring reservations,
bounded retries, and an idempotent report handler. See
[the automation walkthrough](content-automation.md).

See [ADR 0003](decisions/0003-component-oriented-backend.md) for the decision,
tradeoffs, and migration constraints.

See [the Events walkthrough](events-architecture.md) for concrete files,
transaction boundaries, and the remaining integration compromises.

Use cases are classes with constructor-injected ports and an `execute`
method. Write inputs use command DTOs; read inputs use query DTOs when needed.
`app/bootstrap/events.py` composes these classes with SQL adapters. HTTP
dependencies supply request-scoped sessions to those factories, and routers
receive ready-to-use use cases. The match import uses the same composition
module with its existing transaction session.

## Competition conventions and current scope

The component is an organizational boundary containing multiple aggregates,
such as `Team` with memberships/assignments and `TeamMatch` with games and sets.
An aggregate does not need a dedicated folder or an `Aggregate` base class.
`SeasonKey` is a domain value object alongside `Season` and `SeasonHalf`.

```text
core/competition/
  domain/                 seasons.py, teams.py, matches.py, leagues.py
  application/
    commands.py           general writes
    queries.py            general reads
    dto.py                command/query inputs and results
    ports.py              general reader, repository, unit-of-work contracts
    errors.py
    sync/                 sync use cases and their own contracts/DTOs
      commands.py, batches.py, backfill.py, queries.py, mapping.py
      dto.py, imports.py, ports.py, errors.py
bootstrap/
  competition.py          general factories
  competition_sync.py     sync factories, client, backfill, diagnostics
adapters/inbound/http/competition/
  router.py, dependencies.py, schemas.py
```

Use cases expose `execute(command)` or `execute(query)`; parameterless reads
use `execute()` without an empty query object. DTOs are frozen dataclasses.
The domain never imports application DTOs. Sync mapping translates source data
into domain objects; provider JSON stays in the myTischtennis adapter. Existing
external ID fields and import markers remain in the domain models as a documented
compatibility compromise, not a reason to import provider code into the domain.

General and sync reader/repository/unit-of-work ports are separate. Their SQL
implementations may be shared. Repository methods do not commit; write use cases
control the unit of work. Reader methods return projections instead of loading
complete aggregates. Read queries never start an external synchronization.

The HTTP flow is: router `Depends(provide_...)` -> HTTP `dependencies.py` ->
bootstrap factory -> use case with concrete adapters. FastAPI supplies that use
case to the router. The router builds a core query and returns its result through
an explicit response schema. Authorization dependencies run before protected
operations; application errors are translated to HTTP errors by the router.

Implemented reads: `ListSeasons`, `ListTeams`, `GetSchedule`, `GetTeamStandings`,
`GetMatchDetails`, `GetTeamLineup`. Their GET routes are under `/api/competition`;
internal lineup requires ADMIN, while the other reads are public. Core commands
`AssignPlayerToTeam` and `RemovePlayerFromTeam` exist, but their HTTP write routes
are still planned. The frontend has not been extended for these Competition APIs.

See [Competition details and endpoint contracts](competition-domain.md) and
[the sync walkthrough](mytischtennis-architecture.md). For agent entry points and
mandatory conventions, see [backend/AGENTS.md](../backend/AGENTS.md).

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

## Completion of the persistence separation

Competition, Members, and Media table definitions now live exclusively in
`app/adapters/outbound/persistence`. `SeasonHalf`, `GameType`, and
`TeamMatchNoticeCode` are canonical framework-free Competition domain enums.
Model registration, import adapters, maintenance scripts, and tests use the
new locations. Table names, foreign keys, indexes, and migrations are unchanged.

The match-to-event backfill also uses an application class, an injected unit
of work, and the existing outgoing Events contract. HTTP dependencies may
still supply SQL sessions as composition code; controllers and the core do
not issue SQL queries. Members administration and media upload/gallery use
cases remain planned; no unused application classes were added for them.

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

Competition import use cases depend on the outgoing `CompetitionSource` port.
`MyTischtennisSource` implements it and maps validated responses from
`MyTischtennisClient` into framework-free snapshots. SQL repositories and a
unit of work handle persistence separately. Bootstrap composes these adapters.

`SyncCurrent` coordinates the current half-season; `SyncHistory` handles
historical batches. Existing scripts invoke these class-based use cases through
a CLI adapter. Competition and Members ORM tables reside in their outbound
persistence packages. Competition enums are shared framework-free domain types.
Competition also has internal `Season`, `Team`, `TeamMatch`, `Match`, and
`LeagueGroup` entities with their child models. Import use cases load and save
these through `CompetitionRepository`; the external snapshots remain input DTOs.
See [the Competition domain walkthrough](competition-domain.md).
See [the myTischtennis walkthrough](mytischtennis-architecture.md).

A separate content worker runs periodic current-game sync and outbox processing
in independent loops. It is not connected to the FastAPI lifecycle.

## Content automation and planned AI generation

The CMS is intended to assist editors rather than publish generated content
autonomously. The implemented drafting service formats stored match results
as plain text and saves system-authored drafts. Human edits take over authorship
while preserving generation provenance. The worker and manual CLI share the
same report use case. A future generator may combine structured match or event
data with editorial guidance and use the OpenAI API to prepare article drafts.
Generated text must remain traceable, editable, and unpublished until an
authorized editor reviews it.

A separate planned import workflow will accept PDF documents containing club
dates or event schedules. It should extract proposed events, show the source
and any uncertain fields, detect possible duplicates, and require confirmation
before persisting data. The exact PDF extraction and validation architecture
has not yet been decided.
