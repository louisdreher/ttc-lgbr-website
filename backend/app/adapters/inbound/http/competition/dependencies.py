from app.bootstrap import competition as wiring
from app.bootstrap.members import build_assign_player_image
from app.core.members.public import AssignPlayerImage
from app.core.competition.application.commands import AssignPlayerToTeam, RemovePlayerFromTeam
from app.core.competition.application.queries import (
    GetTeamCandidates,
    GetMatchDetails,
    GetSchedule,
    GetTeamLineup,
    GetTeamStandings,
    ListSeasons,
    ListTeams,
)


def provide_assign_player_image() -> AssignPlayerImage:
    return build_assign_player_image()


def provide_get_team_candidates() -> GetTeamCandidates:
    return wiring.build_get_team_candidates()


def provide_assign_player() -> AssignPlayerToTeam:
    return wiring.build_assign_player_to_team()


def provide_remove_player() -> RemovePlayerFromTeam:
    return wiring.build_remove_player_from_team()


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
