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

## Content

The content domain groups calendar entries, editorial articles, and media
around a shared event. The database models and migrations exist. Event
management is available through an administrative API and CMS interface; a
read-only public event API and calendar are also implemented. Article
workflows and media storage are still planned and must not be presented as
completed functionality.

```text
EventCategory
      |
      | 1:n
      v
Event 0..1 ------ 1 TeamMatch
  |
  | 1:n
  |-- Article n ------ m Tag
  |
  | 1:0..1
  `-- Gallery n ------ m MediaAsset
```

### Events and calendar entries

`Event` is both the common editorial context and the calendar entry. It stores
its title, start and optional end, location, description, status, visibility,
and whether an article is expected. `EventStatus` supports `PLANNED`,
`COMPLETED`, `CANCELLED`, and `POSTPONED`. Content visibility is one of
`PUBLIC`, `MEMBERS_ONLY`, or `HIDDEN`.

An event belongs to one `EventCategory`. Categories are stored as data so they
can be ordered and deactivated. `default_report_expected` supplies the initial
value for a newly created event; changing the category later does not
implicitly change existing events.

An event may reference one `TeamMatch`, and that reference is unique. The
competition domain remains the owner of imported match data. The schedule
synchronization creates or updates the related event whenever the
myTischtennis schedule is synchronized. Title, start, end, location, category,
and status follow the imported team match. Description, visibility, and
`report_expected` remain editorial fields and are preserved on later schedule
updates. The same idempotent service can backfill events for existing matches;
the unique `team_match_id` prevents duplicates.

`report_expected` controls whether a completed event should be offered as a
report suggestion. Whether an article already exists is derived from the
article relation instead of being duplicated as another event flag.

Manual events record their creating user when available and may be all-day
entries. The CMS can filter events by year, category, and visibility and can
change visibility in bulk. Imported match events cannot be deleted manually;
their synchronized fields remain owned by the competition integration.

The public event query is deliberately narrower than the administration view:
it returns only `PUBLIC` entries in a requested date range and excludes both
inactive categories and the dedicated team-match category.

### Articles and tags

`Article` stores editorial content and may reference an event. Articles without
an event remain valid for general news and annual reports. Every article has an
author, a unique slug, an `ArticleStatus`, an `ArticleType`, and an independent
visibility setting. A cover image may reference a `MediaAsset`.

Article statuses currently are `DRAFT`, `IN_REVIEW`, `PUBLISHED`, and
`ARCHIVED`. Article types currently are `NEWS`, `MATCH_REPORT`, `EVENT_REPORT`,
`ANNUAL_REPORT`, and `ANNOUNCEMENT`.

`Tag` provides flexible editorial classification independently of event
categories. `ArticleTag` implements the many-to-many relation with a composite
primary key, preventing duplicate assignments. An event category describes
what kind of calendar entry an event is; tags describe the subjects covered by
an article.

The old `published` and `image_url` columns were replaced by `status` and
`cover_image_id`. Existing article routers and request schemas have not yet
been adapted to this model.

### Galleries and media

`MediaAsset` stores file metadata and a storage key, not the file contents. It
also records the original filename, MIME type, size, optional image dimensions,
caption, alternative text, photographer, uploader, and upload time. The actual
storage implementation is planned.

`Gallery` optionally belongs to an event. Its event reference is currently
unique, limiting an event to at most one gallery. `GalleryMedia` relates media
assets to galleries and stores their order and an optional gallery-specific
caption. Its composite primary key prevents the same asset from appearing
twice in one gallery.

Deleting an event sets optional article and gallery event references to null.
Deleting a gallery, article, or tag removes the corresponding association rows.
An event end cannot be earlier than its start.

## Integrity principles

The model uses unique constraints and external IDs to make repeated imports
identifiable. Future model changes should explicitly consider:

- nullability and required values;
- uniqueness and indexes;
- foreign-key delete behavior;
- transaction boundaries during synchronization;
- whether free-form status strings should become enums.
