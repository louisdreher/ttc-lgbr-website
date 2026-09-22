from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import StrEnum


class AssignmentStatus(StrEnum):
    SUBSTITUTE = "Ersatzspieler"


class AssignmentRankingError(ValueError):
    """The registration does not provide an unambiguous lineup order."""


@dataclass(frozen=True)
class RegistrationPosition:
    player_id: int
    team_number: int | None
    rank: str | None

    def sort_key(self) -> tuple[int, int]:
        if self.team_number is None or self.team_number < 1:
            raise AssignmentRankingError("Mannschaftsnummer fehlt oder ist ungültig.")
        if self.rank is None or re.fullmatch(r"[1-9][0-9]*", self.rank) is None:
            raise AssignmentRankingError(f"Ungültiger Meldungsrang: {self.rank!r}")
        return self.team_number, int(self.rank)


@dataclass(kw_only=True)
class Team:
    id: int | None = None
    season_id: int
    league_group_id: int
    mytt_team_id: int
    name: str
    team_number: int | None = None
    category: str | None = None
    memberships: list[TeamMembership] = field(default_factory=list)
    assignments: list[TeamAssignment] = field(default_factory=list)

    def update_identity(self, *, name: str, league_group_id: int) -> None:

        self.name, self.league_group_id = name, league_group_id

    def replace_registration(
        self, *, name: str, number: int | None, memberships: list[TeamMembership]
    ) -> None:

        if name:
            self.name = name

        if number is not None:
            self.team_number = number

        # Last supplied rank wins if the source repeats a player.

        self.memberships = list(
            {member.player_id: member for member in memberships}.values()
        )

        for member in self.memberships:
            member.team_id = self.id

    def assign_player(
        self,
        *,
        player_id: int,
        registration: list[RegistrationPosition],
        position: int | None = None,
        status: AssignmentStatus | None = None,
    ) -> None:

        status = AssignmentStatus(status) if status is not None else None

        assignments = [replace(item) for item in self.assignments]

        existing = next(
            (item for item in assignments if item.player_id == player_id), None
        )

        if existing is None:
            assignments.append(
                TeamAssignment(team_id=self.id, player_id=player_id, status=status)
            )

        else:
            existing.status = status

        if position is not None:
            if type(position) is not int or not 1 <= position <= len(assignments):
                raise AssignmentRankingError(
                    f"Position muss zwischen 1 und {len(assignments)} liegen."
                )
            selected = next(item for item in assignments if item.player_id == player_id)
            assignments.remove(selected)
            assignments.sort(
                key=lambda item: (
                    item.position is None,
                    item.position or 0,
                    item.player_id,
                )
            )
            assignments.insert(position - 1, selected)
        else:
            if not self.category or not self.category.strip():
                raise AssignmentRankingError(
                    "Kategorie fehlt: Bitte eine Position angeben."
                )
            ranks = {}
            for assignment in assignments:
                candidates = {
                    item.sort_key()
                    for item in registration
                    if item.player_id == assignment.player_id
                }
                if len(candidates) != 1:
                    raise AssignmentRankingError(
                        f"Kein eindeutiger Meldungsrang für Spieler {assignment.player_id}."
                    )
                ranks[assignment.player_id] = candidates.pop()
            if len(set(ranks.values())) != len(ranks):
                raise AssignmentRankingError(
                    "Mehrere Spieler haben denselben Meldungsrang."
                )
            assignments.sort(key=lambda item: ranks[item.player_id])

        for assigned_position, assignment in enumerate(assignments, start=1):
            assignment.position = assigned_position

        self.assignments = assignments

    def remove_player(self, player_id: int) -> bool:
        remaining = [item for item in self.assignments if item.player_id != player_id]
        if len(remaining) == len(self.assignments):
            return False
        remaining.sort(
            key=lambda item: (item.position is None, item.position or 0, item.player_id)
        )
        for position, item in enumerate(remaining, start=1):
            item.position = position
        self.assignments = remaining
        return True


def eligible_registration(
    team_number: int | None, registration: list[RegistrationPosition]
) -> dict[int, tuple[int, int]]:
    """Simple internal selection rule; not a complete competition eligibility check."""
    if team_number is None or team_number < 1:
        return {}
    ranks: dict[int, set[tuple[int, int]]] = {}
    invalid: set[int] = set()
    for item in registration:
        try:
            ranks.setdefault(item.player_id, set()).add(item.sort_key())
        except AssignmentRankingError:
            invalid.add(item.player_id)
    unique = {player: next(iter(keys)) for player, keys in ranks.items()
              if len(keys) == 1 and player not in invalid}
    # Conflicting positions cannot provide a reliable ordering.
    counts: dict[tuple[int, int], int] = {}
    for key in unique.values():
        counts[key] = counts.get(key, 0) + 1
    return {player: key for player, key in unique.items()
            if key[0] >= team_number and counts[key] == 1}


@dataclass(kw_only=True)
class TeamMembership:
    team_id: int | None = None

    player_id: int

    rank: str | None = None

    status: str | None = None


@dataclass(kw_only=True)
class TeamAssignment:
    team_id: int | None = None

    player_id: int

    position: int | None = None

    status: str | None = None
