from app.bootstrap import competition as wiring
from app.core.competition.application.queries import (
    GetMatchDetails,
    GetSchedule,
    GetTeamLineup,
    GetTeamStandings,
    ListSeasons,
    ListTeams,
)


def provide_list_seasons() -> ListSeasons:
    return wiring.build_list_seasons()


def provide_list_teams() -> ListTeams:
    return wiring.build_list_teams()


def provide_get_schedule() -> GetSchedule:
    return wiring.build_get_schedule()


def provide_get_team_standings() -> GetTeamStandings:
    return wiring.build_get_team_standings()


def provide_get_match_details() -> GetMatchDetails:
    return wiring.build_get_match_details()


def provide_get_team_lineup() -> GetTeamLineup:
    return wiring.build_get_team_lineup()
