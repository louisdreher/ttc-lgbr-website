from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.competition.domain.imports import (
    ImportedGame,
    ImportedPlayer,
    MeetingDetails,
    SeasonHalf,
)
from app.core.competition.domain.matches import TeamMatch
from app.core.competition.domain.seasons import Season
from app.core.competition.domain.teams import Team, TeamAssignment, TeamMembership


def team_match():
    return TeamMatch(
        id=1,
        team_id=2,
        opponent_name="Gast",
        is_home=True,
        scheduled_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        status="scheduled",
    )


def test_rescheduling_keeps_first_date_and_prefers_explicit_original():
    match = team_match()
    first = match.scheduled_at
    match.reschedule(first + timedelta(days=1))
    match.reschedule(first + timedelta(days=2))
    assert match.original_scheduled_at == first
    earlier = first - timedelta(days=1)
    match.reschedule(first, original_scheduled_at=earlier)
    assert match.original_scheduled_at == earlier


def test_equal_imported_date_without_offset_is_not_a_rescheduling():
    match = team_match()
    match.reschedule(match.scheduled_at.replace(tzinfo=None))
    assert match.original_scheduled_at is None


def test_details_build_lineup_from_unplayed_games_without_database():
    match = team_match()
    own = ImportedPlayer(
        registration_id="NU1", external_id="1", first_name="Anna", last_name="A", rank=1
    )
    opponent = replace(own, first_name="Bea", last_name="B")
    doubles = replace(own, rank=2)
    played = ImportedGame(
        kind="single",
        external_id="game",
        name="1-1",
        home_players=(own, own),
        away_players=(opponent,),
        sets=((1, 11, 8),),
        played=True,
    )
    unplayed = replace(played, kind="double", home_players=(doubles,), played=False)
    details = MeetingDetails(
        completed=True, games=(played, unplayed), score_home=7, score_away=3
    )
    match.import_details(details, {own: 5, doubles: 5}, match.scheduled_at)
    assert (match.lineup[0].position, match.lineup[0].doubles_pair) == (1, 2)
    assert len(match.matches) == 1
    assert len(match.matches[0].participants) == 1
    assert match.matches[0].participants[0].opponent_name == "Bea B"
    assert match.matches[0].sets[0].points_ttc == 11
    assert match.details_imported_at == match.scheduled_at
    before = match.matches
    with pytest.raises(ValueError):
        match.import_details(MeetingDetails(completed=False), {}, match.scheduled_at)
    assert match.matches is before


def test_team_registration_preserves_assignments_and_deduplicates_players():
    team = Team(
        id=1, season_id=1, league_group_id=1, mytt_team_id=1, name="TTC", team_number=2
    )
    assignment = TeamAssignment(team_id=1, player_id=5, position=1)
    team.assignments.append(assignment)
    team.replace_registration(
        name="",
        number=None,
        memberships=[
            TeamMembership(player_id=5, rank="2.1"),
            TeamMembership(player_id=5, rank="2.2"),
        ],
    )
    assert team.name == "TTC" and team.team_number == 2
    assert team.assignments == [assignment]
    assert len(team.memberships) == 1
    assert team.memberships[0].rank == "2.2"
    assert team.memberships[0].team_id == 1


def test_season_is_an_internal_entity_with_a_validated_key():
    season = Season(start_year=2026, end_year=2027, half=SeasonHalf.VR)
    assert season.key.period[0].month == 7
    with pytest.raises(ValueError):
        Season(start_year=2026, end_year=2028, half=SeasonHalf.VR)
