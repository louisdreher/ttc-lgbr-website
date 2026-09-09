from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class LeagueGroup:
    id: int | None = None
    season_id: int
    name: str
    mytt_group_id: int
    mytt_slug: str | None = None
    table: list[LeagueTableEntry] = field(default_factory=list)

    def replace_table(self, entries: list[LeagueTableEntry]) -> None:
        team_ids = [entry.mytt_team_id for entry in entries]
        if len(set(team_ids)) != len(team_ids):
            raise ValueError(
                "Eine Mannschaft darf nur einmal in der Tabelle vorkommen."
            )
        for entry in entries:
            entry.league_group_id = self.id
        self.table = list(entries)


@dataclass(kw_only=True)
class LeagueTableEntry:
    id: int | None = None
    league_group_id: int | None = None
    mytt_team_id: int
    club_id: str
    team_name: str
    position: int
    meetings_count: int
    meetings_won: int
    meetings_tie: int
    meetings_lost: int
    points_won: int
    points_lost: int
    matches_won: int
    matches_lost: int
    sets_won: int
    sets_lost: int
    games_won: int
    games_lost: int
