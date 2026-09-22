import pytest
from sqlmodel import Session

from test_team_assignment import database  # noqa: F401
from app.adapters.outbound.persistence.members.models import PlayerImage
from app.adapters.outbound.persistence.media.models import MediaAsset
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.members import build_assign_player_image, build_get_player_images
from app.bootstrap.competition import build_assign_player_to_team
from app.core.competition.application.dto import AssignPlayerToTeamCommand
from app.core.members.public import (
    AssignPlayerImageCommand, GetPlayerImagesQuery, PlayerImageForbidden,
    PlayerImageAssignmentNotFound, PlayerImageMediaNotFound,
)


@pytest.fixture
def images(database):
    with Session(database) as session:
        session.add(User(id=1, name="Admin", email="image@example.test", password_hash="unused"))
        session.flush()
        for i in range(1, 5):
            session.add(MediaAsset(id=i, storage_key=f"image-{i}", original_filename="image.webp",
                mime_type="image/webp" if i < 4 else "text/plain", file_size=1, uploaded_by_user_id=1))
        session.commit()
    build_assign_player_to_team(lambda: Session(database)).execute(AssignPlayerToTeamCommand(1, 3))
    return database


def test_historical_write_replaces_only_selected_half_and_is_shared(images):
    factory = lambda: Session(images)
    with factory() as session:
        session.add_all([
            PlayerImage(player_id=3, season_start_year=2009, season_half="vr", media_id=1),
            PlayerImage(player_id=3, season_start_year=2026, season_half="rr", media_id=3),
        ])
        session.commit()
    write = build_assign_player_image(factory)
    read = build_get_player_images(factory)
    write.execute(AssignPlayerImageCommand(1, 3, 2, can_manage=True))
    for year, half, expected in [(2025, "rr", 1), (2026, "vr", 2), (2026, "rr", 3), (2027, "vr", 3)]:
        assert read.execute(GetPlayerImagesQuery(frozenset({3}), year, half)) == {3: expected}
    build_assign_player_to_team(factory).execute(AssignPlayerToTeamCommand(2, 3))
    write.execute(AssignPlayerImageCommand(2, 3, 1, can_manage=True))
    assert read.execute(GetPlayerImagesQuery(frozenset({3}), 2026, "vr")) == {3: 1}
    assert read.execute(GetPlayerImagesQuery(frozenset({3}), 2026, "rr")) == {3: 3}


@pytest.mark.parametrize("team,player,media,error", [
    (999, 3, 1, PlayerImageAssignmentNotFound),
    (1, 2, 1, PlayerImageAssignmentNotFound),
    (1, 3, 999, PlayerImageMediaNotFound),
    (1, 3, 4, PlayerImageMediaNotFound),
])
def test_invalid_reference_does_not_write(images, team, player, media, error):
    with pytest.raises(error):
        build_assign_player_image(lambda: Session(images)).execute(
            AssignPlayerImageCommand(team, player, media, can_manage=True))
    with Session(images) as session:
        assert session.get(PlayerImage, (3, 2026, "vr")) is None


def test_unauthorized_write_does_not_open_session():
    def forbidden_session():
        pytest.fail("Unauthorized command must not open a session")
    with pytest.raises(PlayerImageForbidden):
        build_assign_player_image(forbidden_session).execute(AssignPlayerImageCommand(1, 3, 1))
