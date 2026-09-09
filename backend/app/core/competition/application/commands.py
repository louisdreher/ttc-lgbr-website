from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime

from app.core.competition.application.dto import (
    SyncExternalMeetingCommand,
    SyncGroupCommand,
    SyncMeetingCommand,
    SyncScheduleCommand,
)
from app.core.competition.domain.imports import RegistrationTeam, find_registration_team
from app.core.competition.domain.leagues import LeagueGroup, LeagueTableEntry
from app.core.competition.domain.matches import TeamMatch
from app.core.competition.domain.seasons import Season
from app.core.competition.domain.teams import Team, TeamMembership


def persisted_id(entity) -> int:
    if entity.id is None:
        raise RuntimeError("Gespeicherte Entity besitzt keine ID.")
    return entity.id


from app.core.competition.application.ports import (
    CompetitionReader,
    CompetitionSource,
    CompetitionUnitOfWork,
)


class SyncSchedule:
    def __init__(self, source: CompetitionSource, uow: CompetitionUnitOfWork):
        self.source, self.uow = source, uow

    async def execute(self, command: SyncScheduleCommand) -> bool:
        snapshot = await self.source.schedule(command.season)
        if not snapshot.received_count:
            return False
        with self.uow:
            repository = self.uow.repository
            season = repository.find_season(command.season)
            if season is None:
                season = Season(
                    start_year=command.season.start_year,
                    end_year=command.season.end_year,
                    half=command.season.half,
                )
                repository.save_season(season)
            season_id = persisted_id(season)
            for data in snapshot.matches:
                group = repository.find_group(season_id, data.group_external_id)
                if group is None:
                    group = LeagueGroup(
                        season_id=season_id,
                        mytt_group_id=data.group_external_id,
                        name=data.group_name,
                    )
                group.name, group.mytt_slug = data.group_name, data.group_slug
                repository.save_group(group)
                group_id = persisted_id(group)
                team = repository.find_team(season_id, data.team_external_id)
                if team is None:
                    team = Team(
                        season_id=season_id,
                        league_group_id=group_id,
                        mytt_team_id=data.team_external_id,
                        name=data.team_name,
                    )
                team.update_identity(name=data.team_name, league_group_id=group_id)
                repository.save_team(team)
                team_id = persisted_id(team)
                match = repository.find_team_match(data.external_id)
                if match is None:
                    match = TeamMatch.from_schedule(team_id, data)
                else:
                    match.update_schedule(team_id, data)
                repository.save_team_match(match)
                self.uow.events.synchronize(persisted_id(match))
            self.uow.commit()
        return True


class SyncMeeting:
    def __init__(
        self,
        source: CompetitionSource,
        reader: CompetitionReader,
        uow: CompetitionUnitOfWork,
        clock: Callable[[], datetime],
    ):
        self.source, self.reader, self.uow, self.clock = source, reader, uow, clock

    async def execute(self, command: SyncMeetingCommand) -> bool:
        match = self.reader.meeting(command.team_match_id)
        if match.imported and not command.force:
            return False
        details = await self.source.meeting(match.external_id)
        if not details.completed:
            return False
        with self.uow:
            entity = self.uow.repository.get_team_match(match.id)
            if entity is None:
                raise ValueError("Begegnung ist während des Imports verschwunden.")
            player_ids = {}
            for game in details.games:
                for player in game.own_players(entity.is_home):
                    if (not player.absent or game.played) and player not in player_ids:
                        player_ids[player] = self.uow.players.resolve(player)
            entity.import_details(details, player_ids, self.clock())
            self.uow.repository.save_team_match(entity)
            self.uow.commit()
        return True


class SyncExternalMeeting:
    def __init__(self, reader: CompetitionReader, meeting: SyncMeeting):
        self.reader, self.meeting = reader, meeting

    async def execute(self, command: SyncExternalMeetingCommand) -> bool:
        return await self.meeting.execute(
            SyncMeetingCommand(self.reader.match_id(command.external_id), command.force)
        )


class SyncRegistrations:
    def __init__(
        self,
        source: CompetitionSource,
        reader: CompetitionReader,
        uow: CompetitionUnitOfWork,
    ):
        self.source, self.reader, self.uow = source, reader, uow

    async def execute(self, command: SyncGroupCommand) -> bool:
        group = self.reader.group(command.league_group_id)
        if not group.external_slug:
            return False
        registrations = await self.source.registrations(group)
        if not registrations:
            return False
        with self.uow:
            if self.uow.repository.get_group(group.id) is None:
                raise ValueError("Ligagruppe ist während des Imports verschwunden.")
            teams = self.uow.repository.teams_in_group(group.id)
            processed = False
            for registration in registrations:
                team_id = find_registration_team(
                    [
                        RegistrationTeam(persisted_id(t), t.name, t.team_number)
                        for t in teams
                    ],
                    registration,
                )
                if team_id is None:
                    continue
                team = next(t for t in teams if t.id == team_id)
                memberships = [
                    TeamMembership(
                        player_id=self.uow.players.resolve(
                            entry.player, update_names=True
                        ),
                        rank=entry.rank,
                        status=entry.status,
                    )
                    for entry in registration.players
                ]
                team.replace_registration(
                    name=registration.team_name,
                    number=registration.team_number,
                    memberships=memberships,
                )
                self.uow.repository.save_team(team)
                processed = True
            if not processed:
                return False
            self.uow.commit()
        return True


class SyncStandings:
    def __init__(
        self,
        source: CompetitionSource,
        reader: CompetitionReader,
        uow: CompetitionUnitOfWork,
    ):
        self.source, self.reader, self.uow = source, reader, uow

    async def execute(self, command: SyncGroupCommand) -> bool:
        if command.skip_existing and self.reader.has_standings(command.league_group_id):
            return False
        group = self.reader.group(command.league_group_id, require_team=True)
        rows = await self.source.standings(group)
        # An unavailable table is not an instruction to delete the saved table.
        if not rows:
            return False
        with self.uow:
            entity = self.uow.repository.get_group(group.id)
            if entity is None:
                raise ValueError("Ligagruppe ist während des Imports verschwunden.")
            entries = []
            for row in rows:
                values = asdict(row)
                values["mytt_team_id"] = values.pop("external_team_id")
                entries.append(LeagueTableEntry(**values))
            entity.replace_table(entries)
            self.uow.repository.save_group(entity)
            self.uow.commit()
        return True
