from datetime import datetime, timedelta, timezone

import pytest

from app.core.competition.domain.matches import TeamMatch
from app.core.competition.domain.seasons import Season, SeasonHalf
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


def test_record_result_uses_domain_objects_and_rejects_incomplete_result():
    from app.core.competition.domain.matches import GameType, Match, MatchLineup

    entity = team_match()
    matches = [Match(sequence=1, game_type=GameType.SINGLE)]
    lineup = [MatchLineup(player_id=5, position=1)]
    entity.record_result(
        completed=True, matches=matches, lineup=lineup, score_ttc=7, score_opponent=3
    )
    assert entity.matches == matches
    assert entity.lineup == lineup
    assert (entity.score_ttc, entity.score_opponent) == (7, 3)
    assert entity.details_imported_at is None
    with pytest.raises(ValueError):
        entity.record_result(completed=False, matches=[], lineup=[])
    assert entity.matches == matches
    assert entity.lineup == lineup
