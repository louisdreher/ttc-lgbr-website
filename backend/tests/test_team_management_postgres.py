from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from alembic import command
from sqlmodel import Session

from test_outbox_postgres import postgres_database, seed_report_match  # noqa: F401
from app.adapters.outbound.persistence.competition.teams import Team, TeamMembership
from app.adapters.outbound.persistence.members.models import Member, Player
from app.bootstrap.competition import build_assign_player_to_team, build_get_team_lineup
from app.core.competition.application.dto import AssignPlayerToTeamCommand, GetTeamLineupQuery


def test_parallel_assignments_preserve_both_players(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "head")
    seed_report_match(engine)
    with Session(engine) as session:
        team = session.get(Team, 1)
        team.team_number = 1
        team.category = "H"
        session.add(team)
        for player_id in (1, 2):
            session.add(Member(id=player_id, first_name="Test", last_name=str(player_id)))
        session.flush()
        for player_id in (1, 2):
            session.add(Player(id=player_id, member_id=player_id))
        session.flush()
        for player_id in (1, 2):
            session.add(TeamMembership(team_id=1, player_id=player_id, rank=str(player_id)))
        session.commit()
    barrier = Barrier(2)

    def assign(player_id):
        barrier.wait(timeout=5)
        build_assign_player_to_team(lambda: Session(engine)).execute(AssignPlayerToTeamCommand(1, player_id))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(assign, player_id) for player_id in (1, 2)]
        for future in futures:
            future.result(timeout=15)
    lineup = build_get_team_lineup(lambda: Session(engine)).execute(GetTeamLineupQuery(1))
    assert [(player.player_id, player.position) for player in lineup.players] == [(1, 1), (2, 2)]
