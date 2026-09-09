import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.adapters.outbound.competition.events import CompetitionMatchEvents
from app.adapters.outbound.persistence.competition.leagues import LeagueGroup
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.seasons import Season, SeasonHalf
from app.adapters.outbound.persistence.competition.teams import Team
from app.adapters.outbound.persistence.events.models import (
    Event,
    EventCategory,
    EventStatus,
)
from app.bootstrap.competition import build_backfill_match_events
from app.bootstrap.events import build_sync_match_event
from app.core.competition.application.dto import BackfillMatchEventsCommand


class CompetitionMatchEventsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[
                Season.__table__,
                LeagueGroup.__table__,
                Team.__table__,
                TeamMatch.__table__,
                EventCategory.__table__,
                Event.__table__,
            ],
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_rollback_removes_match_event_and_automatically_created_category(self):
        with Session(self.engine) as session:
            match = self._create_team_match(
                session, datetime(2026, 9, 1, tzinfo=timezone.utc)
            )
            CompetitionMatchEvents(
                session, build_sync_match_event(session)
            ).synchronize(match.id)
            session.rollback()
        with Session(self.engine) as session:
            self.assertEqual(session.exec(select(TeamMatch)).all(), [])
            self.assertEqual(session.exec(select(Event)).all(), [])
            self.assertEqual(session.exec(select(EventCategory)).all(), [])

    def test_backfill_of_committed_matches_preserves_editorial_fields(self):
        with Session(self.engine) as session:
            match = self._create_team_match(
                session, datetime(2026, 9, 1, tzinfo=timezone.utc)
            )
            CompetitionMatchEvents(
                session, build_sync_match_event(session)
            ).synchronize(match.id)
            event = session.exec(select(Event)).one()
            row = session.get(Event, event.id)
            row.description = "Beibehalten"
            row.report_expected = False
            from app.core.content.types import Visibility

            row.visibility = Visibility.HIDDEN
            match.status = "abgesagt"
            session.commit()
        self.assertEqual(
            build_backfill_match_events(lambda: Session(self.engine)).execute(
                BackfillMatchEventsCommand()
            ),
            (0, 1),
        )
        with Session(self.engine) as session:
            row = session.exec(select(Event)).one()
            self.assertEqual(row.status, EventStatus.CANCELLED)
            self.assertEqual(row.description, "Beibehalten")
            self.assertFalse(row.report_expected)
            self.assertEqual(row.visibility, Visibility.HIDDEN)

    def test_sync_one_creates_and_updates_one_event(self) -> None:
        scheduled_at = datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc)

        with Session(self.engine) as session:
            team_match = self._create_team_match(session, scheduled_at)
            sync = CompetitionMatchEvents(session, build_sync_match_event(session))

            created = sync.synchronize(team_match.id)
            event = session.exec(select(Event)).one()

            self.assertTrue(created)
            self.assertEqual(event.title, "TTC Langen-Brombach – Gastverein")
            self.assertEqual(event.location, "Sporthalle, Hauptstraße 1, Erbach")
            self.assertEqual(event.status, EventStatus.PLANNED)

            session.get(Event, event.id).description = "Redaktioneller Hinweis"
            team_match.scheduled_at = scheduled_at + timedelta(days=1)
            team_match.is_completed = True

            created = sync.synchronize(team_match.id)
            updated_event = session.exec(select(Event)).one()

            self.assertFalse(created)
            self.assertEqual(updated_event.id, event.id)
            self.assertEqual(updated_event.starts_at, team_match.scheduled_at)
            self.assertEqual(updated_event.status, EventStatus.COMPLETED)
            self.assertEqual(updated_event.description, "Redaktioneller Hinweis")
            self.assertEqual(len(session.exec(select(Event)).all()), 1)

    def test_backfill_can_limit_sync_to_completed_matches(self) -> None:
        scheduled_at = datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc)

        with Session(self.engine) as session:
            completed = self._create_team_match(session, scheduled_at)
            completed.is_completed = True
            self._create_team_match(
                session,
                scheduled_at + timedelta(days=1),
                meeting_id=2,
            )

            completed_id = completed.id
            session.commit()
        created, updated = build_backfill_match_events(
            lambda: Session(self.engine)
        ).execute(BackfillMatchEventsCommand(True))
        with Session(self.engine) as session:
            self.assertEqual((created, updated), (1, 0))
            events = session.exec(select(Event)).all()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].team_match_id, completed_id)

    def test_sync_ignores_historical_end_time_before_start(self) -> None:
        scheduled_at = datetime(2006, 1, 20, 17, 0, tzinfo=timezone.utc)

        with Session(self.engine) as session:
            team_match = self._create_team_match(session, scheduled_at)
            team_match.ended_at = datetime(1970, 1, 1, 17, 0, tzinfo=timezone.utc)

            CompetitionMatchEvents(
                session, build_sync_match_event(session)
            ).synchronize(team_match.id)
            event = session.exec(select(Event)).one()

            self.assertIsNone(event.ends_at)

    @staticmethod
    def _create_team_match(
        session: Session,
        scheduled_at: datetime,
        meeting_id: int = 1,
    ) -> TeamMatch:
        season = session.exec(select(Season)).first()

        if season is None:
            season = Season(start_year=2026, end_year=2027, half=SeasonHalf.VR)
            session.add(season)
            session.flush()

        league_group = LeagueGroup(
            season_id=season.id,
            name=f"Bezirksliga {meeting_id}",
            mytt_group_id=meeting_id,
        )
        session.add(league_group)
        session.flush()

        team = Team(
            season_id=season.id,
            league_group_id=league_group.id,
            mytt_team_id=meeting_id,
            name="TTC Langen-Brombach",
        )
        session.add(team)
        session.flush()

        team_match = TeamMatch(
            team_id=team.id,
            mytt_meeting_id=meeting_id,
            opponent_name="Gastverein",
            is_home=True,
            scheduled_at=scheduled_at,
            status="scheduled",
            venue_name="Sporthalle",
            venue_street="Hauptstraße 1",
            venue_city="Erbach",
        )
        session.add(team_match)
        session.flush()

        return team_match


if __name__ == "__main__":
    unittest.main()
