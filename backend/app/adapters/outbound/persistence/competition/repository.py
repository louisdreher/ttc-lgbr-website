"""Map Competition entities to SQL rows; no import decisions or commits."""

from dataclasses import fields
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.adapters.outbound.persistence.competition import (
    leagues,
    matches,
    seasons,
    teams,
)
from app.core.competition.domain import leagues as domain_leagues
from app.core.competition.domain import matches as domain_matches
from app.core.competition.domain import seasons as domain_seasons
from app.core.competition.domain import teams as domain_teams
from app.core.competition.domain.seasons import SeasonKey


def _entity(entity_type, row):
    values = {
        field.name: getattr(row, field.name)
        for field in fields(entity_type)
        if field.name in type(row).model_fields
    }
    for name, value in values.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            values[name] = value.replace(tzinfo=timezone.utc)
    return entity_type(**values)


class SqlCompetitionRepository:
    def __init__(self, session: Session):
        self.session = session

    def _save(self, model, entity):
        values = {name: getattr(entity, name) for name in model.model_fields}
        keys = [column.name for column in model.__table__.primary_key]
        identity = tuple(values[key] for key in keys)
        row = (
            self.session.get(model, identity)
            if all(value is not None for value in identity)
            else None
        )
        if row is None:
            row = model(**values)
        else:
            row.sqlmodel_update(values)
        self.session.add(row)
        self.session.flush()
        if "id" in keys:
            entity.id = row.id

    def _children(self, model, parent_key, parent_id, children):
        existing = list(
            self.session.exec(
                select(model).where(getattr(model, parent_key) == parent_id)
            ).all()
        )
        keys = [column.name for column in model.__table__.primary_key]
        desired = {
            tuple(
                getattr(child, key) if key != parent_key else parent_id for key in keys
            )
            for child in children
        }
        for row in existing:
            if tuple(getattr(row, key) for key in keys) not in desired:
                self.session.delete(row)
        # Delete before insertion to preserve existing unique constraints.
        self.session.flush()
        for child in children:
            setattr(child, parent_key, parent_id)
            self._save(model, child)

    def find_season(self, key: SeasonKey) -> domain_seasons.Season | None:
        row = self.session.exec(
            select(seasons.Season).where(
                seasons.Season.start_year == key.start_year,
                seasons.Season.end_year == key.end_year,
                seasons.Season.half == key.half,
            )
        ).first()
        return _entity(domain_seasons.Season, row) if row is not None else None

    def save_season(self, season: domain_seasons.Season) -> None:
        self._save(seasons.Season, season)

    def find_group(
        self, season_id: int, external_id: int
    ) -> domain_leagues.LeagueGroup | None:
        row = self.session.exec(
            select(leagues.LeagueGroup).where(
                leagues.LeagueGroup.season_id == season_id,
                leagues.LeagueGroup.mytt_group_id == external_id,
            )
        ).first()
        return self.get_group(row.id) if row is not None else None

    def get_group(self, group_id: int) -> domain_leagues.LeagueGroup | None:
        row = self.session.get(leagues.LeagueGroup, group_id)
        if row is None:
            return None
        group = _entity(domain_leagues.LeagueGroup, row)
        group.table = [
            _entity(domain_leagues.LeagueTableEntry, entry)
            for entry in self.session.exec(
                select(leagues.LeagueTableEntry)
                .where(leagues.LeagueTableEntry.league_group_id == group_id)
                .order_by(leagues.LeagueTableEntry.position)
            ).all()
        ]
        return group

    def save_group(self, group: domain_leagues.LeagueGroup) -> None:
        self._save(leagues.LeagueGroup, group)
        self._children(
            leagues.LeagueTableEntry, "league_group_id", group.id, group.table
        )

    def find_team(self, season_id: int, external_id: int) -> domain_teams.Team | None:
        row = self.session.exec(
            select(teams.Team).where(
                teams.Team.season_id == season_id,
                teams.Team.mytt_team_id == external_id,
            )
        ).first()
        return self._team(row) if row is not None else None

    def teams_in_group(self, group_id: int) -> list[domain_teams.Team]:
        return [
            self._team(row)
            for row in self.session.exec(
                select(teams.Team).where(teams.Team.league_group_id == group_id)
            ).all()
        ]

    def _team(self, row):
        team = _entity(domain_teams.Team, row)
        team.memberships = [
            _entity(domain_teams.TeamMembership, item)
            for item in self.session.exec(
                select(teams.TeamMembership).where(
                    teams.TeamMembership.team_id == team.id
                )
            ).all()
        ]
        team.assignments = [
            _entity(domain_teams.TeamAssignment, item)
            for item in self.session.exec(
                select(teams.TeamAssignment).where(
                    teams.TeamAssignment.team_id == team.id
                )
            ).all()
        ]
        return team

    def save_team(self, team: domain_teams.Team) -> None:
        self._save(teams.Team, team)
        self._children(teams.TeamMembership, "team_id", team.id, team.memberships)
        self._children(teams.TeamAssignment, "team_id", team.id, team.assignments)

    def registration_for_category(
        self, season_id: int, category: str
    ) -> list[domain_teams.RegistrationPosition]:
        rows = self.session.exec(
            select(teams.TeamMembership, teams.Team.team_number)
            .join(teams.Team, teams.TeamMembership.team_id == teams.Team.id)
            .where(teams.Team.season_id == season_id, teams.Team.category == category)
        ).all()
        return [
            domain_teams.RegistrationPosition(member.player_id, number, member.rank)
            for member, number in rows
        ]

    def get_team(self, team_id: int) -> domain_teams.Team | None:
        row = self.session.get(teams.Team, team_id)
        return self._team(row) if row is not None else None

    def find_team_match(self, external_id: int) -> domain_matches.TeamMatch | None:
        row = self.session.exec(
            select(matches.TeamMatch).where(
                matches.TeamMatch.mytt_meeting_id == external_id
            )
        ).first()
        return self.get_team_match(row.id) if row is not None else None

    def get_team_match(self, match_id: int) -> domain_matches.TeamMatch | None:
        row = self.session.get(matches.TeamMatch, match_id)
        if row is None:
            return None
        match = _entity(domain_matches.TeamMatch, row)
        match.notices = [
            _entity(domain_matches.TeamMatchNotice, item)
            for item in self.session.exec(
                select(matches.TeamMatchNotice).where(
                    matches.TeamMatchNotice.team_match_id == match_id
                )
            ).all()
        ]
        match.lineup = [
            _entity(domain_matches.MatchLineup, item)
            for item in self.session.exec(
                select(matches.MatchLineup).where(
                    matches.MatchLineup.team_match_id == match_id
                )
            ).all()
        ]
        for item in self.session.exec(
            select(matches.Match)
            .where(matches.Match.team_match_id == match_id)
            .order_by(matches.Match.sequence)
        ).all():
            game = _entity(domain_matches.Match, item)
            game.participants = [
                _entity(domain_matches.MatchParticipant, child)
                for child in self.session.exec(
                    select(matches.MatchParticipant).where(
                        matches.MatchParticipant.match_id == game.id
                    )
                ).all()
            ]
            game.sets = [
                _entity(domain_matches.SetResult, child)
                for child in self.session.exec(
                    select(matches.SetResult)
                    .where(matches.SetResult.match_id == game.id)
                    .order_by(matches.SetResult.set_number)
                ).all()
            ]
            match.matches.append(game)
        return match

    def save_team_match(self, match: domain_matches.TeamMatch) -> None:
        self._save(matches.TeamMatch, match)
        self._children(
            matches.TeamMatchNotice, "team_match_id", match.id, match.notices
        )
        self._children(matches.MatchLineup, "team_match_id", match.id, match.lineup)
        ids = {game.id for game in match.matches if game.id is not None}
        for row in self.session.exec(
            select(matches.Match).where(matches.Match.team_match_id == match.id)
        ).all():
            if row.id not in ids:
                self._children(matches.MatchParticipant, "match_id", row.id, [])
                self._children(matches.SetResult, "match_id", row.id, [])
                self.session.delete(row)
        self.session.flush()
        for game in match.matches:
            game.team_match_id = match.id
            self._save(matches.Match, game)
            self._children(
                matches.MatchParticipant, "match_id", game.id, game.participants
            )
            self._children(matches.SetResult, "match_id", game.id, game.sets)

    def match_ids(self, *, completed_only: bool = False) -> list[int]:
        query = select(matches.TeamMatch.id).order_by(matches.TeamMatch.id)
        if completed_only:
            query = query.where(matches.TeamMatch.is_completed.is_(True))
        return list(self.session.exec(query).all())
