import app.model_registry  # noqa: F401
import pytest
from app.adapters.outbound.persistence.competition.seasons import Season
from app.bootstrap.competition import build_list_seasons
from app.core.competition.application.dto import SeasonSummary
from app.core.competition.domain.seasons import SeasonHalf
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seasons.db'}")
    try:
        SQLModel.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()


def test_seasons_sorted_newest_first_with_return_half_first(database):
    with Session(database) as session:
        session.add_all(
            [
                Season(id=1, start_year=2025, end_year=2026, half=SeasonHalf.RR),
                Season(id=2, start_year=2026, end_year=2027, half=SeasonHalf.VR),
                Season(id=3, start_year=2025, end_year=2026, half=SeasonHalf.VR),
                Season(id=4, start_year=2026, end_year=2027, half=SeasonHalf.RR),
                Season(id=5, start_year=2027, end_year=2028, half=SeasonHalf.VR),
            ]
        )
        session.commit()
    result = build_list_seasons(lambda: Session(database)).execute()
    assert result == [
        SeasonSummary(5, 2027, 2028, SeasonHalf.VR),
        SeasonSummary(4, 2026, 2027, SeasonHalf.RR),
        SeasonSummary(2, 2026, 2027, SeasonHalf.VR),
        SeasonSummary(1, 2025, 2026, SeasonHalf.RR),
        SeasonSummary(3, 2025, 2026, SeasonHalf.VR),
    ]
    assert all(isinstance(item.half, SeasonHalf) for item in result)


def test_no_seasons_returns_empty_list(database):
    assert build_list_seasons(lambda: Session(database)).execute() == []
