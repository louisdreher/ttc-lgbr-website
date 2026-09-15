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

router = APIRouter(prefix="/api/competition", tags=["Competition"])
lineup_admin = require_any_role(RoleName.ADMIN)
PositiveId = Annotated[int, Path(gt=0)]


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
