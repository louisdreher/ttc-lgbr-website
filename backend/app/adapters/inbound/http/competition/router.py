from datetime import date
from typing import Annotated

from app.adapters.inbound.http.auth.permissions import require_any_role
from app.adapters.inbound.http.competition.dependencies import (
    provide_get_match_details,
    provide_get_schedule,
    provide_get_team_lineup,
    provide_get_team_standings,
    provide_list_seasons,
    provide_list_teams,
)
from app.adapters.inbound.http.competition.schemas import (
    MatchDetailsRead,
    ScheduledMatchSummaryRead,
    SeasonSummaryRead,
    StandingSummaryRead,
    TeamLineupRead,
    TeamSummaryRead,
)
from app.core.competition.application.dto import (
    GetMatchDetailsQuery,
    GetScheduleQuery,
    GetTeamLineupQuery,
    GetTeamStandingsQuery,
    ListTeamsQuery,
)
from app.core.competition.application.errors import (
    MatchNotFoundError,
    TeamNotFoundError,
)
from app.core.competition.application.queries import (
    GetMatchDetails,
    GetSchedule,
    GetTeamLineup,
    GetTeamStandings,
    ListSeasons,
    ListTeams,
)
from app.core.users.public import RoleName
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from app.adapters.inbound.http.competition.dependencies import (
    provide_get_team_candidates, provide_assign_player, provide_remove_player,
)
from app.adapters.inbound.http.competition.schemas import PlayerCandidateRead
from app.core.competition.application.commands import AssignPlayerToTeam, RemovePlayerFromTeam
from app.core.competition.application.queries import GetTeamCandidates
from app.core.competition.application.dto import AssignPlayerToTeamCommand, RemovePlayerFromTeamCommand
from app.core.competition.application.errors import PlayerNotFoundError
from app.core.competition.domain.teams import AssignmentRankingError
from app.adapters.inbound.http.competition.dependencies import provide_assign_player_image
from app.adapters.inbound.http.competition.schemas import PlayerImageWrite
from app.core.members.public import (
    AssignPlayerImage, AssignPlayerImageCommand, PlayerImageAssignmentNotFound,
    PlayerImageForbidden, PlayerImageMediaNotFound,
)

router = APIRouter(prefix="/api/competition", tags=["Competition"])
lineup_admin = require_any_role(RoleName.ADMIN)
PositiveId = Annotated[int, Path(gt=0)]


@router.put(
    "/teams/{team_id}/lineup/{player_id}/image", status_code=204,
    dependencies=[Depends(lineup_admin)],
)
def assign_player_image(
    team_id: PositiveId, player_id: PositiveId, body: PlayerImageWrite,
    usecase: Annotated[AssignPlayerImage, Depends(provide_assign_player_image)],
):
    try:
        usecase.execute(AssignPlayerImageCommand(team_id, player_id, body.media_id, can_manage=True))
    except PlayerImageForbidden as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (PlayerImageAssignmentNotFound, PlayerImageMediaNotFound) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/teams/{team_id}/candidates", response_model=list[PlayerCandidateRead],
            dependencies=[Depends(lineup_admin)])
def get_team_candidates(team_id: PositiveId,
    usecase: Annotated[GetTeamCandidates, Depends(provide_get_team_candidates)]):
    try:
        return usecase.execute(GetTeamLineupQuery(team_id))
    except TeamNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/teams/{team_id}/lineup/{player_id}", status_code=204,
            dependencies=[Depends(lineup_admin)])
def assign_player(team_id: PositiveId, player_id: PositiveId,
    usecase: Annotated[AssignPlayerToTeam, Depends(provide_assign_player)]):
    try:
        usecase.execute(AssignPlayerToTeamCommand(team_id, player_id))
    except (TeamNotFoundError, PlayerNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AssignmentRankingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete("/teams/{team_id}/lineup/{player_id}", status_code=204,
               dependencies=[Depends(lineup_admin)])
def remove_player(team_id: PositiveId, player_id: PositiveId,
    usecase: Annotated[RemovePlayerFromTeam, Depends(provide_remove_player)]):
    try:
        usecase.execute(RemovePlayerFromTeamCommand(team_id, player_id))
    except TeamNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/seasons", response_model=list[SeasonSummaryRead])
def list_seasons(usecase: Annotated[ListSeasons, Depends(provide_list_seasons)]):
    return usecase.execute()


@router.get("/teams", response_model=list[TeamSummaryRead])
def list_teams(
    usecase: Annotated[ListTeams, Depends(provide_list_teams)],
    season_id: Annotated[int, Query(gt=0)],
    category: str | None = None,
):
    return usecase.execute(ListTeamsQuery(season_id, category))


@router.get("/schedule", response_model=list[ScheduledMatchSummaryRead])
def get_schedule(
    usecase: Annotated[GetSchedule, Depends(provide_get_schedule)],
    date_from: date,
    date_to: date,
    team_ids: Annotated[list[Annotated[int, Query(gt=0)]] | None, Query()] = None,
    category: str | None = None,
):
    if date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="Das Startdatum darf nicht nach dem Enddatum liegen.",
        )
    return usecase.execute(
        GetScheduleQuery(
            date_from, date_to, tuple(team_ids) if team_ids else None, category
        )
    )


@router.get("/teams/{team_id}/standings", response_model=list[StandingSummaryRead])
def get_team_standings(
    team_id: PositiveId,
    usecase: Annotated[GetTeamStandings, Depends(provide_get_team_standings)],
):
    return usecase.execute(GetTeamStandingsQuery(team_id))


@router.get("/matches/{match_id}", response_model=MatchDetailsRead)
def get_match_details(
    match_id: PositiveId,
    usecase: Annotated[GetMatchDetails, Depends(provide_get_match_details)],
):
    try:
        return usecase.execute(GetMatchDetailsQuery(match_id))
    except MatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get(
    "/teams/{team_id}/lineup",
    response_model=TeamLineupRead,
    dependencies=[Depends(lineup_admin)],
)
def get_team_lineup(
    team_id: PositiveId,
    usecase: Annotated[GetTeamLineup, Depends(provide_get_team_lineup)],
):
    try:
        return usecase.execute(GetTeamLineupQuery(team_id))
    except TeamNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
