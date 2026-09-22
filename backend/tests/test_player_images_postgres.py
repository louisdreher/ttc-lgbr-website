"""Schema checks on disposable PostgreSQL databases only."""

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from test_outbox_postgres import postgres_database  # noqa: F401
from app.adapters.outbound.persistence.members.models import Member, Player, PlayerImage
from app.adapters.outbound.persistence.media.models import MediaAsset
from app.adapters.outbound.persistence.users.models import User


def test_concurrent_image_changes_across_teams_share_one_history_entry(postgres_database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlmodel import select
    from test_outbox_postgres import seed_report_match
    from app.adapters.outbound.persistence.competition.teams import Team, TeamAssignment
    from app.bootstrap.members import build_assign_player_image
    from app.core.members.public import AssignPlayerImageCommand

    engine, config = postgres_database
    command.upgrade(config, "head")
    seed_report_match(engine)
    with Session(engine) as session:
        first_team = session.get(Team, 1)
        session.add(Team(id=2, season_id=first_team.season_id,
            league_group_id=first_team.league_group_id, mytt_team_id=2, name="Second team"))
        session.add(Member(id=1, first_name="Test", last_name="Player"))
        session.add(User(id=900001, email="image@example.test", name="Admin", password_hash="unused"))
        session.flush()
        session.add(Player(id=1, member_id=1))
        for media_id in (1, 2):
            session.add(MediaAsset(id=media_id, storage_key=f"image-{media_id}", original_filename="test.webp",
                mime_type="image/webp", file_size=10, uploaded_by_user_id=900001))
        session.flush()
        for team_id in (1, 2):
            session.add(TeamAssignment(team_id=team_id, player_id=1, position=1))
        session.commit()
    barrier = Barrier(2)

    def change(team_id):
        barrier.wait(timeout=5)
        build_assign_player_image(lambda: Session(engine)).execute(
            AssignPlayerImageCommand(team_id, 1, team_id, can_manage=True))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(change, team_id) for team_id in (1, 2)]
        for future in futures:
            future.result(timeout=15)
    with Session(engine) as session:
        rows = session.exec(select(PlayerImage)).all()
        assert len(rows) == 1
        assert (rows[0].season_start_year, rows[0].season_half) == (2026, "vr")
        assert rows[0].media_id in (1, 2)


def test_empty_database_migration_matches_models(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "head")
    command.check(config)
    assert inspect(engine).get_pk_constraint("player_image")["constrained_columns"] == [
        "player_id", "season_start_year", "season_half"
    ]


def test_upgrade_constraints_and_downgrade_preserve_existing_data(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "e5a37b62c846")
    with Session(engine) as session:
        session.add(Member(id=1, first_name="Test", last_name="Player"))
        session.add(User(id=900001, email="image@example.test", name="Admin", password_hash="test"))
        session.flush()
        session.add(Player(id=1, member_id=1))
        for media_id in (1, 2):
            session.add(MediaAsset(
                id=media_id, storage_key=f"{media_id}.webp", original_filename="test.jpg",
                mime_type="image/webp", file_size=10, uploaded_by_user_id=900001,
            ))
        session.commit()
    command.upgrade(config, "f6b48c73d957")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO player_image VALUES (1, 2008, 1)"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        assert session.get(PlayerImage, (1, 2008, "vr")).media_id == 1
        session.add(PlayerImage(player_id=1, season_start_year=2009, season_half="vr", media_id=1))
        session.add(PlayerImage(player_id=1, season_start_year=2014, season_half="vr", media_id=2))
        session.commit()
        for statement in (
            "INSERT INTO player_image (player_id, season_start_year, media_id, season_half) VALUES (1, 2014, 1, 'vr')",
            "INSERT INTO player_image (player_id, season_start_year, media_id, season_half) VALUES (999, 2026, 1, 'vr')",
            "INSERT INTO player_image (player_id, season_start_year, media_id, season_half) VALUES (1, 2026, 999, 'vr')",
            "DELETE FROM player WHERE id = 1",
            "DELETE FROM media_asset WHERE id = 1",
        ):
            with pytest.raises(IntegrityError):
                session.execute(text(statement))
                session.commit()
            session.rollback()
        for half in ("invalid", None):
            with pytest.raises(IntegrityError):
                session.execute(text(
                    "INSERT INTO player_image (player_id, season_start_year, media_id, season_half) "
                    "VALUES (1, 2026, 1, :half)"
                ), {"half": half})
                session.commit()
            session.rollback()
        session.add(PlayerImage(player_id=1, season_start_year=2014, season_half="rr", media_id=2))
        session.commit()
        image = session.get(PlayerImage, (1, 2014, "vr"))
        image.media_id = 1
        session.commit()
        assert session.get(PlayerImage, (1, 2009, "vr")).media_id == 1
        assert session.get(MediaAsset, 2) is not None
    with pytest.raises(RuntimeError, match="Downgrade blocked"):
        command.downgrade(config, "f6b48c73d957")
    with Session(engine) as session:
        assert session.get(PlayerImage, (1, 2014, "rr")).media_id == 2
        assert session.get(PlayerImage, (1, 2014, "vr")).media_id == 1
        session.delete(session.get(PlayerImage, (1, 2014, "rr")))
        session.commit()
    command.downgrade(config, "f6b48c73d957")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM player_image")).scalar() == 3
    command.downgrade(config, "e5a37b62c846")
    assert "player_image" not in inspect(engine).get_table_names()
    with Session(engine) as session:
        assert session.get(Player, 1) is not None
        assert session.get(MediaAsset, 1) is not None
    command.upgrade(config, "head")
    command.check(config)
