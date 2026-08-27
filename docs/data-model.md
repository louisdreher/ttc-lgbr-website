# Data model

## Identity and membership

`Member` stores club membership and contact information. A `Player` represents
the table-tennis-specific identity of a member and may carry external
myTischtennis identifiers. `PlayerRating` stores a player's QTTR value for an
effective date.

A `User` is an application login. It may be linked one-to-one to a `Member`.
Users receive roles through the `UserRoleLink` association table.

Available role names currently are:

- `ADMIN`
- `EDITOR`
- `TEAM_REPORTER`

`RefreshSession` stores hashed refresh tokens and their rotation family for
authentication sessions.

## Competition structure

```text
Season
  |-- LeagueGroup
  |     |-- Team
  |     `-- LeagueTableEntry
  `-- Team
        `-- TeamMatch
              |-- MatchLineup
              |-- Match
              |     |-- MatchParticipant
              |     `-- SetResult
              `-- TeamMatchNotice

Member -- Player -- PlayerRating
              |-- TeamMembership
              |-- TeamAssignment
              |-- MatchLineup
              `-- MatchParticipant
```

### Seasons and teams

A season identifies a start year, end year, and half-season (`vr` or `rr`). A
league group belongs to one season. Teams belong to a season and league group
and retain their external myTischtennis team ID.

`TeamMembership` represents the registered squad and rank information.
`TeamAssignment` is a separate assignment concept, although its exact long-term
distinction from membership still needs to be documented as the feature grows.

### Team matches and individual matches

`TeamMatch` represents a scheduled club encounter. It stores the opponent,
location, schedule, state, result, and myTischtennis meeting ID.

The details of a team match are split into:

- `MatchLineup` for the club lineup;
- `Match` for singles or doubles in sequence;
- `MatchParticipant` for participants;
- `SetResult` for individual set scores;
- `TeamMatchNotice` for imported notice codes.

`details_imported_at` indicates whether detailed meeting data has already been
imported.

### League tables

`LeagueTableEntry` stores a snapshot row for a league group, including table
position and won/lost counts for meetings, points, matches, sets, and games.

## Articles

`Article` is intended to store public news and editorial content. The model and
some routes exist, but creation and publication behavior are not yet fully
implemented. Current fields and endpoints should therefore not be treated as a
finished content-management contract.

## Integrity principles

The model uses unique constraints and external IDs to make repeated imports
identifiable. Future model changes should explicitly consider:

- nullability and required values;
- uniqueness and indexes;
- foreign-key delete behavior;
- transaction boundaries during synchronization;
- whether free-form status strings should become enums.

