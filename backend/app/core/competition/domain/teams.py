from __future__ import annotations

from dataclasses import dataclass, field


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
