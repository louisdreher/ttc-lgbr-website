from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.core.competition.application.imports import (
    ImportedGame,
    ImportedPlayer,
    MeetingDetails,
)
from app.core.competition.application.usecases.sync.mapping import apply_meeting
from app.core.competition.domain.matches import TeamMatch


def team_match():
    return TeamMatch(
        id=1,
        team_id=2,
        opponent_name="Gast",
        is_home=True,
        scheduled_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        status="scheduled",
    )


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
    apply_meeting(match, details, {own: 5, doubles: 5}, match.scheduled_at)
    assert (match.lineup[0].position, match.lineup[0].doubles_pair) == (1, 2)
    assert len(match.matches) == 1
    assert len(match.matches[0].participants) == 1
    assert match.matches[0].participants[0].opponent_name == "Bea B"
    assert match.matches[0].sets[0].points_ttc == 11
    assert match.details_imported_at == match.scheduled_at
    before = match.matches
    with pytest.raises(ValueError):
        apply_meeting(match, MeetingDetails(completed=False), {}, match.scheduled_at)
    assert match.matches is before


def test_away_result_translates_scores_and_missing_player_is_atomic():
    entity = team_match()
    entity.is_home = False
    own = ImportedPlayer(
        registration_id="own", external_id="1", first_name="A", last_name="B"
    )
    opponent = replace(own, registration_id="other", first_name="C")
    game = ImportedGame(
        kind="single",
        external_id="game",
        name=None,
        home_players=(opponent,),
        away_players=(own,),
        sets=((1, 8, 11),),
        played=True,
    )
    details = MeetingDetails(completed=True, games=(game,), score_home=3, score_away=7)
    with pytest.raises(KeyError):
        apply_meeting(entity, details, {}, entity.scheduled_at)
    assert entity.matches == []
    assert entity.details_imported_at is None
    apply_meeting(entity, details, {own: 5}, entity.scheduled_at)
    assert (entity.score_ttc, entity.score_opponent) == (7, 3)
    assert entity.matches[0].sets[0].points_ttc == 11
    assert entity.matches[0].participants[0].player_id == 5
