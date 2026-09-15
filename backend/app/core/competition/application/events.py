"""Public event contracts; delivery belongs to the messaging adapters."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ImportOrigin(StrEnum):
    """The initiating workflow, not the age of the match or its data provider."""

    CURRENT = "CURRENT"
    HISTORY = "HISTORY"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class TeamMatchResultsImported:
    """First successful detail import; consumers may act only after commit.

    occurred_at is the import time in UTC, not the time the match ended.
    event_id identifies one occurrence and must survive delivery retries.
    """

    event_id: UUID
    team_match_id: int
    occurred_at: datetime
    import_origin: ImportOrigin
