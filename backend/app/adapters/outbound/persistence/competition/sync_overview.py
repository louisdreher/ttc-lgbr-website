from dataclasses import asdict

from app.adapters.outbound.persistence.competition.automation import (
    MatchReloadRequest,
    SyncAutomation,
    aware,
    decode_state,
    reload_domain,
)
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.teams import Team
from app.core.competition.application.sync.automation.dto import (
    MatchReloadStatus,
    SyncMatchOverview,
    SyncMatchSummary,
)
from app.core.competition.domain.match_reload import ReloadTarget
from sqlmodel import select


class SqlSyncMatchOverviewReader:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def read(self, now):
        with self.session_factory() as session:
            automation = session.get(SyncAutomation, 1)
            last_run = decode_state(automation.state).last_run if automation else None
            query = (
                select(TeamMatch, Team, MatchReloadRequest)
                .join(Team, Team.id == TeamMatch.team_id)
                .outerjoin(
                    MatchReloadRequest, MatchReloadRequest.team_match_id == TeamMatch.id
                )
            )

            def summaries(statement):
                result = []
                for match, team, request in session.exec(statement).all():
                    target = ReloadTarget(
                        match.id,
                        match.is_completed,
                        aware(match.details_imported_at),
                        match.mytt_meeting_id,
                    )
                    reason = target.blocked_reason()
                    if (
                        reason is None
                        and request
                        and request.status in {"requested", "running"}
                    ):
                        reason = "Ein Nachlade-Auftrag ist bereits offen."
                    if (
                        reason is None
                        and last_run
                        and last_run.status == "running"
                        and last_run.match_id == match.id
                    ):
                        reason = (
                            "Für dieses Spiel läuft bereits ein automatischer Abruf."
                        )
                    result.append(
                        SyncMatchSummary(
                            match.id,
                            team.id,
                            team.name,
                            match.opponent_name,
                            match.is_home,
                            aware(match.scheduled_at),
                            match.is_completed,
                            aware(match.details_imported_at),
                            MatchReloadStatus(**asdict(reload_domain(request)))
                            if request
                            else None,
                            reason is None,
                            reason,
                        )
                    )
                return result

            return SyncMatchOverview(
                imported=summaries(
                    query.where(TeamMatch.details_imported_at.is_not(None))
                    .order_by(TeamMatch.details_imported_at.desc(), TeamMatch.id)
                    .limit(10)
                ),
                missing_details=summaries(
                    query.where(
                        TeamMatch.is_completed.is_(True),
                        TeamMatch.details_imported_at.is_(None),
                    ).order_by(TeamMatch.scheduled_at, TeamMatch.id)
                ),
                upcoming=summaries(
                    query.where(
                        TeamMatch.scheduled_at > now,
                        TeamMatch.is_completed.is_(False),
                        TeamMatch.details_imported_at.is_(None),
                    )
                    .order_by(TeamMatch.scheduled_at, TeamMatch.id)
                    .limit(3)
                ),
            )
