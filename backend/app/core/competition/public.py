"""Explicit contract for integration adapters."""

from app.core.competition.application.sync.imports import ImportedPlayer
from app.core.competition.application.sync.ports import ImportedPlayers

__all__ = ["ImportedPlayer", "ImportedPlayers"]
