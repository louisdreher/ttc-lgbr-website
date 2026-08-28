# ADR 0002: Event-centered content domain

## Status

Accepted

## Context

The existing club website is rarely maintained because creating and combining
calendar entries, reports, match results, and photo galleries is cumbersome.
These records are commonly related to the same real-world occasion, such as a
team match, tournament, trip, or club event. At the same time, the calendar
also contains milestones for which no report is expected, and some articles do
not belong to an event at all.

The application therefore needs a common context without merging competition,
editorial, and media data into one oversized model. It must also preserve the
myTischtennis integration as the authoritative source for imported match data.

## Decision

- Introduce `app/domains/content` with the subdomains `events`, `articles`, and
  `media`.
- Use `Event` as both the shared editorial context and the calendar entry.
- Let an event optionally reference one `TeamMatch`; keep `TeamMatch` owned by
  the competition domain and independent of content.
- Use `report_expected` on each event to control future report suggestions.
  Event categories provide only the initial default for that flag.
- Let articles and galleries optionally reference an event so general content
  remains possible.
- Keep event categories separate from article tags. An event has one category,
  while an article may have many tags through `ArticleTag`.
- Represent the editorial purpose with `ArticleType` and the publication
  workflow with `ArticleStatus`.
- Store media metadata in `MediaAsset` and gallery membership in
  `GalleryMedia`; keep the actual file storage behind a future storage service.
- Limit an event to at most one gallery initially through a unique event
  reference.
- Use shared content visibility values: `PUBLIC`, `MEMBERS_ONLY`, and `HIDDEN`.

## Consequences

- Calendar views, report suggestions, articles, and galleries can use the same
  event context.
- General articles and standalone galleries remain possible without creating
  artificial events.
- The competition domain does not acquire dependencies on CMS concepts.
- A synchronization workflow must create or update events for team matches
  while preserving manually maintained editorial fields.
- Effective visibility across an event and its related content must be enforced
  consistently by future backend services.
- Existing article endpoints and schemas must be adapted before the new model
  is usable through the API.
- Media uploads require later decisions about storage, validation, image
  variants, deletion, and access control.
- Supporting multiple galleries per event later requires removing the unique
  constraint from `Gallery.event_id` and adapting the user interface.
