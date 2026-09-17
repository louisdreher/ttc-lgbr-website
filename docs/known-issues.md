# Known issues and deferred work

This document records known limitations that are intentionally not solved yet.
They should not be interpreted as accidental omissions or completed features.

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

Backend and frontend CMS workflow implemented; media management planned.

Preparation, saving/claiming drafts, submission, publication, own/editorial lists,
and visibility-filtered public/member reads are implemented. See
[Articles](articles-architecture.md) for the API and role rules. Apply migration
`c9e15f30a624` before using the new workflow. Editorial visibility changes,
archiving, restoration as a draft, and deletion are implemented. Media upload,
rich-text editing and version-conflict detection remain unimplemented.

## Media storage not implemented

### Status

Planned.

Media and gallery metadata are represented in the data model, but upload,
storage, image processing, access control, and lifecycle handling still require
an implementation and an explicit storage decision.

## Public website content is partly provisional

### Status

In progress.

The public layout and routes exist, and the event calendar is connected to the
backend. Several other public and internal pages still contain provisional
content or UI scaffolding and should not be presented as finished features.

## AI-assisted drafts and PDF imports not implemented

### Status

Planned.

The intended CMS includes two further automation workflows: creating editable
drafts for match and event reports through the OpenAI API, and extracting
candidate events from PDF documents. Neither workflow is currently
implemented. Both require validation, transparent error handling, duplicate
detection where applicable, and explicit human approval before publication or
data import.
