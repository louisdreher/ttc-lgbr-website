# ADR 0001: Access tokens and refresh-token cookies

## Status

Accepted

## Context

The application needs authenticated API requests while avoiding persistent
storage of bearer access tokens in the browser. It should also preserve login
across a page reload and support server-side session revocation.

## Decision

- FastAPI issues a short-lived JWT access token.
- Angular keeps the access token only in application memory.
- A longer-lived random refresh token is sent as an HttpOnly cookie.
- PostgreSQL stores only the SHA-256 hash of the refresh token.
- Refresh tokens are rotated after use and grouped into token families.
- Angular attempts a refresh during application initialization and reloads the
  current user afterward.
- Backend dependencies enforce authentication and roles. Frontend guards are
  used for navigation only.

## Consequences

- A page reload requires a refresh request because the access token is not
  persisted.
- JavaScript cannot directly read the refresh cookie, reducing token exposure
  during an XSS incident.
- Refresh sessions must be stored and cleaned up in PostgreSQL.
- Cookie security settings must be configured correctly for production.
- Concurrent refreshes and replay handling require careful transactional
  behavior.

