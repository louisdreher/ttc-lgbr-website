"""Explicit contract for integration adapters."""

from app.core.competition.application.sync.imports import ImportedPlayer
from app.core.competition.application.sync.ports import ImportedPlayers

from app.core.competition.application.events import ImportOrigin, TeamMatchResultsImported

__all__ = ["ImportedPlayer", "ImportedPlayers", "ImportOrigin", "TeamMatchResultsImported"]
