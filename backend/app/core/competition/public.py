"""Explicit contract for integration adapters."""

from app.core.competition.application.dto import GetMatchDetailsQuery, MatchDetails
from app.core.competition.application.events import (
    ImportOrigin,
    TeamMatchResultsImported,
)
from app.core.competition.application.queries import GetMatchDetails
from app.core.competition.application.sync.imports import ImportedPlayer
from app.core.competition.application.sync.ports import ImportedPlayers

__all__ = [
    "GetMatchDetails",
    "GetMatchDetailsQuery",
    "ImportOrigin",
    "ImportedPlayer",
    "ImportedPlayers",
    "MatchDetails",
    "TeamMatchResultsImported",
]
