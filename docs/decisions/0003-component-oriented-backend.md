# ADR 0003: Component-oriented backend architecture

## Status

Accepted

## Context

The backend is already grouped around domain-oriented areas such as content,
competition, users, and members. Within those areas, however, FastAPI delivery
code, application workflows, domain rules, SQLModel persistence, and external
integration details are not always separated. Several service functions
depend directly on SQLModel sessions and queries, while routers sometimes
contain validation that should apply independently of HTTP.

The project is intended both as a club website and as a learning project. Its
architecture should therefore make dependency direction and domain ownership
visible without introducing infrastructure that has no concrete purpose.
A full rewrite would create unnecessary risk, particularly around SQLModel
models, Alembic history, compatibility imports, synchronization scripts, and
partially implemented frontend features.

## Decision

- Adopt a component-oriented Ports and Adapters architecture as the target for
  new backend functionality and code deliberately selected for refactoring.
- Organize application-core code under `app/components`, with domain-oriented
  components containing `application` and `domain` packages.
- Place delivery mechanisms such as FastAPI and CLI code under
  `app/adapters/inbound` and concrete persistence or external-service
  implementations under `app/adapters/outbound`.
- Reserve `app/platform` for application-wide technical setup such as
  settings, database engine creation, logging, and composition support.
- Treat this structure as an incremental target. Existing `app/domains`,
  `app/core`, `app/auth`, and `app/integrations` code remains valid until a
  separate change deliberately migrates it.
- Use the article component as the first component developed with the new
  structure. Do not migrate other components as a side effect of that work.
- Keep domain code independent of FastAPI, Pydantic transport schemas,
  SQLModel, SQLAlchemy, and concrete external services.
- Let application code depend on its domain model and application-owned ports.
  Inbound and outbound adapters may depend inward on those contracts.
- Keep FastAPI `Depends` in inbound adapters or composition wiring. It may
  construct request-scoped adapters and use cases but must not appear in
  domain or application code.
- Let controllers call use cases and query objects directly. Do not introduce
  a command bus or query bus.
- Model write inputs with commands when bundling the use-case input is useful.
  Write use cases use domain behavior and repository ports.
- Model reads with query objects and, where useful, dedicated reader ports
  returning optimized result DTOs. Queries do not need to load complete domain
  objects for display-only data.
- Keep HTTP request and response schemas in the HTTP adapter. Keep application
  commands, queries, and result DTOs transport-independent when they cross a
  meaningful boundary.
- Do not require an input-port interface for every use case. Introduce an
  interface only when it defines a useful boundary or enables a concrete
  variation.
- Require an explicit public contract, port, or event for communication across
  components. Do not import another component's internal implementation.
- Introduce events and a shared kernel only for concrete cross-component
  workflows. Keep any shared kernel minimal.
- Preserve Alembic history. Changes to persistence models must use new
  migrations and retain required compatibility imports during incremental
  migration.

## Consequences

- Domain and application behavior can be tested without FastAPI or a live
  database when their ports are replaced with test implementations.
- Framework, ORM, and external-service details become easier to identify and
  change without leaking them into the application core.
- The distinction between commands, queries, transport schemas, domain
  objects, and persistence models becomes explicit.
- New functionality requires additional files, mapping, dependency wiring,
  and architectural judgment compared with direct router-to-SQLModel code.
- The repository will temporarily contain both the previous structure and the
  target structure. Documentation and reviews must distinguish current state
  from migrated code.
- Existing SQLModel classes may initially remain combined domain and
  persistence models where separating them would add disproportionate risk.
  Such compromises must be explicit and may be revisited when domain behavior
  requires an independent model.
- A bus, event dispatcher, unit of work, shared kernel, or generic abstraction
  is not justified merely by this decision. Each requires a concrete need and
  a separate, reviewable design choice.
- Architecture rules should eventually be supported by import or dependency
  tests, but selecting such tooling is outside this decision.
