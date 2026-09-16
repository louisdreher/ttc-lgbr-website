from dataclasses import asdict
from datetime import datetime, timezone

import sqlalchemy as sa
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.core.competition.domain.sync_automation import (
    ScheduledMatch,
    SyncRun,
    SyncSettings,
    SyncState,
)
from sqlmodel import Field, SQLModel, select


class SyncAutomation(SQLModel, table=True):
    __tablename__ = "mytt_sync_automation"
    __table_args__ = (sa.CheckConstraint("id = 1", name="ck_mytt_sync_singleton"),)
    id: int = Field(primary_key=True)
    settings: dict = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    state: dict = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    heartbeat_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )


class MatchPoll(SQLModel, table=True):
    __tablename__ = "mytt_match_poll"
    team_match_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("team_match.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    scheduled_at: datetime = Field(sa_type=sa.DateTime(timezone=True))
    attempted_at: datetime = Field(sa_type=sa.DateTime(timezone=True))


def aware(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value is not None and value.tzinfo is None
        else value
    )


def encode(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    return value


def decode_state(data):
    values = dict(data)
    for key in ("last_nightly_slot", "last_nightly_success_at", "last_error_at"):
        if values.get(key):
            values[key] = datetime.fromisoformat(values[key])
    for key in ("last_run", "nightly_run"):
        if values.get(key):
            run = dict(values[key])
            for name in ("started_at", "finished_at"):
                if run.get(name):
                    run[name] = datetime.fromisoformat(run[name])
            values[key] = SyncRun(**run)
    return SyncState(**values)


class SqlAutomationRepository:
    def __init__(self, session, *, write):
        self.session, self.write = session, write
        self._row = None

    def _get(self):
        if self._row is None:
            query = select(SyncAutomation).where(SyncAutomation.id == 1)
            if self.write:
                query = query.with_for_update()
            self._row = self.session.exec(query).one()
        return self._row

    def settings(self):
        return SyncSettings(**self._get().settings)

    def save_settings(self, settings):
        self._get().settings = asdict(settings)

    def state(self):
        return decode_state(self._get().state)

    def save_state(self, state):
        self._get().state = encode(asdict(state))

    def heartbeat(self):
        return aware(self._get().heartbeat_at)

    def save_heartbeat(self, now):
        self._get().heartbeat_at = now

    def candidates(self, since):
        rows = self.session.exec(
            select(TeamMatch, MatchPoll)
            .outerjoin(MatchPoll, MatchPoll.team_match_id == TeamMatch.id)
            .where(
                TeamMatch.details_imported_at.is_(None),
                TeamMatch.mytt_meeting_id.is_not(None),
                TeamMatch.scheduled_at >= since,
            )
        ).all()
        return [
            ScheduledMatch(
                m.id,
                aware(m.scheduled_at),
                aware(p.attempted_at)
                if p and aware(p.scheduled_at) == aware(m.scheduled_at)
                else None,
            )
            for m, p in rows
        ]

    def attempted(self, match, now):
        poll = self.session.get(MatchPoll, match.id)
        if poll is None:
            poll = MatchPoll(
                team_match_id=match.id,
                scheduled_at=match.scheduled_at,
                attempted_at=now,
            )
        else:
            poll.scheduled_at, poll.attempted_at = match.scheduled_at, now
        self.session.add(poll)


class SqlAutomationUnitOfWork:
    def __init__(self, session_factory, *, write=True):
        self.session_factory, self.write = session_factory, write

    def __enter__(self):
        self.session = self.session_factory()
        self.repository = SqlAutomationRepository(self.session, write=self.write)
        return self

    def __exit__(self, *args):
        self.session.rollback()
        self.session.close()

    def commit(self):
        self.session.commit()
