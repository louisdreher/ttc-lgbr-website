import pytest
from sqlmodel import Session

from test_team_assignment import database, lineup  # noqa: F401
from app.adapters.outbound.persistence.competition.teams import TeamMembership
from app.bootstrap.competition import build_get_team_candidates, build_assign_player_to_team
from app.core.competition.application.dto import AssignPlayerToTeamCommand, GetTeamLineupQuery
from app.core.competition.application.errors import TeamNotFoundError
from app.core.competition.domain.teams import AssignmentRankingError, RegistrationPosition, eligible_registration


def test_candidates_sorted_numerically_and_scoped_to_half(database):
    candidates = build_get_team_candidates(lambda: Session(database))
    assert [p.player_id for p in candidates.execute(GetTeamLineupQuery(1))] == [2, 1, 3]
    # Team 2 cannot use players registered in team 1.
    assert [p.player_id for p in candidates.execute(GetTeamLineupQuery(2))] == [3]
    # The other half has its own registration.
    assert [p.player_id for p in candidates.execute(GetTeamLineupQuery(3))] == [4, 1]


def test_assigned_players_are_hidden_and_rejected_registration_is_atomic(database):
    assign = build_assign_player_to_team(lambda: Session(database))
    assign.execute(AssignPlayerToTeamCommand(2, 3))
    assert build_get_team_candidates(lambda: Session(database)).execute(GetTeamLineupQuery(2)) == []
    with pytest.raises(AssignmentRankingError):
        assign.execute(AssignPlayerToTeamCommand(2, 1))
    assert lineup(database) == []  # Team 1 is unaffected.
    with Session(database) as session:
        assert session.get(TeamMembership, (1, 1)) is not None


def test_missing_team(database):
    with pytest.raises(TeamNotFoundError):
        build_get_team_candidates(lambda: Session(database)).execute(GetTeamLineupQuery(999))


def test_bad_and_conflicting_registrations_are_not_offered():
    registration = [
        RegistrationPosition(1, 2, "4"),
        RegistrationPosition(2, 3, "10"),
        RegistrationPosition(3, 3, "2"),
        RegistrationPosition(4, 4, "bad"),
        RegistrationPosition(5, 4, "1"),
        RegistrationPosition(5, 5, "1"),
        RegistrationPosition(6, 4, "2"),
        RegistrationPosition(7, 4, "2"),
    ]
    assert eligible_registration(3, registration) == {2: (3, 10), 3: (3, 2)}
    assert eligible_registration(None, registration) == {}
