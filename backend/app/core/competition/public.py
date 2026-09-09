"""Explicit contract for integration adapters."""

from app.core.competition.application.ports import ImportedPlayers
from app.core.competition.domain.imports import ImportedPlayer

__all__ = ["ImportedPlayer", "ImportedPlayers"]
