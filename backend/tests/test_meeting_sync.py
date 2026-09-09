import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.model_registry  # noqa: F401 -- register foreign-key targets
from app.adapters.outbound.mytischtennis.source import MyTischtennisSource
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.repository import (
    SqlCompetitionRepository,
)
from app.bootstrap.competition import build_competition
from app.core.competition.application.dto import SyncMeetingCommand


@pytest.fixture
def meeting_database():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        match = TeamMatch(
            team_id=1,
            mytt_meeting_id=123,
            opponent_name="Gastverein",
            is_home=True,
            status="scheduled",
            scheduled_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        session.add(match)
        session.commit()
        match_id = match.id
    yield engine, match_id
    engine.dispose()


def completed_meeting():
    # No play_mode: venue and score must still be processed.
    return {
        "data": {
            "is_completed": True,
            "start_date": "2026-09-01T18:00:00+00:00",
            "end_date": "2026-09-01T20:00:00+00:00",
            "location": {
                "label": "Sporthalle",
                "street": "Hauptstraße 1",
                "city": "Erbach",
            },
            "matches_home": 7,
            "matches_guest": 3,
            "match": [],
        }
    }


@pytest.mark.parametrize("is_home, expected_score", [(True, (7, 3)), (False, (3, 7))])
def test_completed_meeting_import_and_repeat_skip(
    meeting_database, is_home, expected_score
):
    engine, match_id = meeting_database
    with Session(engine) as session:
        match = session.get(TeamMatch, match_id)
        match.is_home = is_home
        session.commit()
    client = AsyncMock()
    client.get_meeting.return_value = completed_meeting()
    sync = build_competition(
        session_factory=lambda: Session(engine), source=MyTischtennisSource(client, "1")
    ).meeting
    assert asyncio.run(sync.execute(SyncMeetingCommand(match_id))) is True
    assert asyncio.run(sync.execute(SyncMeetingCommand(match_id))) is False
    client.get_meeting.assert_awaited_once_with(meeting_id=123)
    with Session(engine) as session:
        match = session.get(TeamMatch, match_id)
        assert match.is_completed
        assert match.details_imported_at is not None
        assert match.venue_name == "Sporthalle"
        assert match.venue_city == "Erbach"
        assert (match.score_ttc, match.score_opponent) == expected_score
        assert match.started_at.hour == 18
        assert match.ended_at.hour == 20


def test_failed_detail_import_rolls_back_match_update(meeting_database):
    engine, match_id = meeting_database
    client = AsyncMock()
    client.get_meeting.return_value = completed_meeting()
    sync = build_competition(
        session_factory=lambda: Session(engine), source=MyTischtennisSource(client, "1")
    ).meeting
    original = SqlCompetitionRepository.save_team_match

    def fail_after_flush(self, *args):
        original(self, *args)
        raise RuntimeError("invalid lineup")

    with (
        patch.object(SqlCompetitionRepository, "save_team_match", fail_after_flush),
        pytest.raises(RuntimeError, match="invalid lineup"),
    ):
        asyncio.run(sync.execute(SyncMeetingCommand(match_id)))
    with Session(engine) as session:
        match = session.get(TeamMatch, match_id)
        assert match.details_imported_at is None
        assert not match.is_completed
        assert match.venue_name is None
