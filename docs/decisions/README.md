# Architecture decision records

Architecture decision records (ADRs) explain important technical decisions and
their consequences. They complement the current-state documentation in
`docs/architecture.md`.

Use a new numbered file when a decision has lasting architectural impact:

```text
0001-short-title.md
0002-next-decision.md
```

Each ADR should contain:

- status (`Proposed`, `Accepted`, `Superseded`, or `Rejected`);
- context and problem;
- decision;
- consequences and tradeoffs.

Open problems without an accepted decision belong in
`docs/known-issues.md`, not in an ADR.

## Records

- [0001: Access tokens and refresh-token cookies](0001-authentication.md)
- [0002: Event-centered content domain](0002-content-domain.md)
