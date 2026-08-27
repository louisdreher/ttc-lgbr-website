# Architecture

## Overview

The application is currently organized as a browser-based Angular frontend, a
FastAPI backend, and a PostgreSQL database.

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
- `app/domains/articles`: public and administrative article endpoints;
- `app/domains/competition`: seasons, teams, matches, and league tables;
- `app/integrations/mytischtennis`: external API access and synchronization;
- `app/jobs`: planned scheduled synchronization.

`app.*` is the canonical Python import path. Backend commands therefore need
to run with `backend/` as the working directory, or otherwise make that package
root available explicitly.

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

The current migration chain was created for an already existing development
database. Its baseline is empty and cannot recreate the full schema on a new
database. This limitation is documented but intentionally not fixed yet.

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

