import asyncio
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta

from app.core.competition.application.events import ImportOrigin
from app.core.competition.application.sync.automation.dto import (
    MatchReloadStatus,
    RequestMatchReloadCommand,
    UpdateSyncSettingsCommand,
)
from app.core.competition.application.sync.automation.errors import (
    MatchReloadConflictError,
    ReloadMatchNotFoundError,
)
from app.core.competition.application.sync.automation.ports import (
    AutomationUnitOfWork,
    ScheduledCompetition,
)
from app.core.competition.application.sync.dto import (
    ImportSummary,
    SyncGroupCommand,
    SyncMeetingCommand,
    SyncScheduleCommand,
)
from app.core.competition.application.sync.ports import CompetitionReader
from app.core.competition.domain.match_reload import MatchReload
from app.core.competition.domain.seasons import SeasonKey
from app.core.competition.domain.sync_automation import BERLIN, SyncRun


class UpdateSyncSettings:
    def __init__(self, uow_factory: Callable[[], AutomationUnitOfWork]):
        self.uow_factory = uow_factory

    def execute(self, command: UpdateSyncSettingsCommand):
        with self.uow_factory() as uow:
            uow.repository.save_settings(command.settings)
            uow.commit()
        return command.settings


class RequestSync:
    """Coalesce requests into one pending general sync, also while paused."""

    def __init__(self, uow_factory: Callable[[], AutomationUnitOfWork]):
        self.uow_factory = uow_factory

    def execute(self):
        with self.uow_factory() as uow:
            state = uow.repository.state()
            state.requested = True
            uow.repository.save_state(state)
            uow.commit()


class RecordWorkerHeartbeat:
    def __init__(
        self,
        uow_factory: Callable[[], AutomationUnitOfWork],
        clock: Callable[[], datetime],
    ):
        self.uow_factory, self.clock = uow_factory, clock

    def execute(self):
        with self.uow_factory() as uow:
            uow.repository.save_heartbeat(self.clock())
            uow.commit()


class RequestMatchReload:
    def __init__(
        self,
        uow_factory: Callable[[], AutomationUnitOfWork],
        clock: Callable[[], datetime],
    ):
        self.uow_factory, self.clock = uow_factory, clock

    def execute(self, command: RequestMatchReloadCommand) -> MatchReloadStatus:
        with self.uow_factory() as uow:
            repo = uow.repository
            # Serialize enqueueing with worker selection, without holding locks during I/O.
            state = repo.state()
            target = repo.reload_target(command.team_match_id)
            if target is None:
                raise ReloadMatchNotFoundError()
            reason = target.blocked_reason()
            if reason:
                raise MatchReloadConflictError(reason)
            request = repo.reload_request(target.id)
            if request and request.is_open:
                return MatchReloadStatus(**asdict(request))
            if (
                state.last_run
                and state.last_run.status == "running"
                and state.last_run.match_id == target.id
            ):
                raise MatchReloadConflictError(
                    "Für dieses Spiel läuft bereits ein automatischer Abruf."
                )
            if request is None:
                request = MatchReload(target.id, self.clock())
            else:
                request.request(self.clock())
            repo.save_reload(request)
            uow.commit()
            return MatchReloadStatus(**asdict(request))


class RunScheduledSync:
    """One due job per tick. The caller MUST hold the cross-process sync lock."""

    def __init__(
        self,
        uow_factory: Callable[[], AutomationUnitOfWork],
        competition: ScheduledCompetition,
        reader: CompetitionReader,
        clock: Callable[[], datetime],
        sleep=asyncio.sleep,
    ):
        self.uow_factory, self.competition, self.reader = (
            uow_factory,
            competition,
            reader,
        )
        self.clock, self.sleep = clock, sleep

    async def execute(self) -> ImportSummary:
        now = self.clock()
        with self.uow_factory() as uow:
            repo = uow.repository
            settings, state = repo.settings(), repo.state()
            # Owning the advisory lock proves any persisted running job was abandoned.
            if state.last_run and state.last_run.status == "running":
                abandoned = state.last_run
                abandoned.status, abandoned.finished_at = "failed", now
                abandoned.errors = ["Worker unterbrochen; Lauf nicht abgeschlossen."]
                state.last_error, state.last_error_at = abandoned.errors[0], now
                if abandoned.kind != "match":
                    state.nightly_run = abandoned
                    state.requested = True
                repo.save_state(state)
            for interrupted in repo.running_reloads():
                interrupted.recover()
                repo.save_reload(interrupted)
            reload_request = repo.next_reload()
            kind, match = None, None
            slot = settings.nightly_slot(now)
            if reload_request:
                kind = "match"
                reload_request.start(now)
                repo.save_reload(reload_request)
            elif state.requested:
                kind = "manual"
                state.requested = False
            elif settings.enabled and (
                state.last_nightly_slot is None or state.last_nightly_slot < slot
            ):
                kind = "nightly"
            elif settings.enabled:
                candidates = repo.candidates(
                    now
                    - timedelta(
                        minutes=settings.result_delay_minutes,
                        hours=settings.result_retry_window_hours,
                    )
                )
                due = sorted(
                    (
                        m
                        for m in candidates
                        if m.due_at(settings) <= now <= m.expires_at(settings)
                    ),
                    key=lambda m: (m.due_at(settings), m.id),
                )
                if due:
                    kind, match = "match", due[0]
            if kind is None:
                uow.commit()
                return ImportSummary()
            match_id = (
                reload_request.team_match_id
                if reload_request
                else match.id
                if match
                else None
            )
            run = SyncRun(kind, now, match_id)
            state.last_run = run
            if match:
                repo.attempted(match, now)
            elif kind != "match":
                state.last_nightly_slot, state.nightly_run = slot, run
            repo.save_state(state)
            uow.commit()

        try:
            if reload_request:
                imported, error = await self._reload_match(reload_request.team_match_id)
                run.imported, run.skipped = int(imported), int(not imported)
                if error:
                    run.errors.append(error)
            elif match:
                imported = await self.competition.meeting.execute(
                    SyncMeetingCommand(match.id, import_origin=ImportOrigin.CURRENT)
                )
                run.imported, run.skipped = int(imported), int(not imported)
                if not imported and self.clock() + timedelta(
                    minutes=settings.result_retry_minutes
                ) > match.expires_at(settings):
                    run.errors.append(
                        "Keine vollständigen Ergebnisse bis zum Ende des Abruffensters."
                    )
            else:
                await self._general(run, settings)
        except Exception as error:  # noqa: BLE001 -- persist job failure, keep later jobs runnable
            # Provider/SQL error strings may contain credentials or raw payloads.
            run.errors.append(type(error).__name__)
        run.finished_at = self.clock()
        run.status = (
            ("partial" if run.imported else "failed") if run.errors else "succeeded"
        )
        if match and run.skipped and not run.errors:
            run.status = "waiting"
        with self.uow_factory() as uow:
            state = uow.repository.state()
            state.last_run = run
            if reload_request:
                current = uow.repository.reload_request(reload_request.team_match_id)
                if current is not None:  # deleting the match cascades to its request
                    current.finish(run.finished_at, "; ".join(run.errors) or None)
                    uow.repository.save_reload(current)
            if kind != "match":
                state.nightly_run = run
                if not run.errors:
                    state.last_nightly_success_at = run.finished_at
            if run.errors:
                state.last_error, state.last_error_at = (
                    "; ".join(run.errors),
                    run.finished_at,
                )
            uow.repository.save_state(state)
            uow.commit()
        return ImportSummary(
            run.imported, run.skipped, [match_id or 0] if run.errors else []
        )

    async def _reload_match(self, match_id: int) -> tuple[bool, str | None]:
        with self.uow_factory() as uow:
            target = uow.repository.reload_target(match_id)
        if target is None:
            return False, "Das angeforderte Spiel wurde gelöscht."
        if target.details_imported_at is not None:
            return (
                False,
                None,
            )  # e.g. crash after result commit, before job confirmation
        reason = target.blocked_reason()
        if reason:
            return False, reason
        imported = await self.competition.meeting.execute(
            SyncMeetingCommand(match_id, import_origin=ImportOrigin.MANUAL)
        )
        if imported:
            return True, None
        with self.uow_factory() as uow:
            target = uow.repository.reload_target(match_id)
        if target and target.details_imported_at is not None:
            return False, None  # another explicit import completed in the meantime
        return False, "myTischtennis liefert noch keine vollständigen Ergebnisse."

    async def _general(self, run, settings):
        season = SeasonKey.current(self.clock().astimezone(BERLIN).date())
        imported = await self.competition.schedule.execute(SyncScheduleCommand(season))
        if not imported:
            run.errors.append("Keine Spielplandaten erhalten.")
            return
        run.imported += 1
        season_id = self.reader.season_id(season)
        if season_id is None:
            run.errors.append(
                "Aktuelle Halbserie nach Spielplanimport nicht vorhanden."
            )
            return
        operations = []
        if settings.include_tables:
            operations.append(("table", self.competition.standings))
        if settings.include_registrations:
            operations.append(("registration", self.competition.registrations))
        for group_id in self.reader.group_ids(season_id):
            for label, operation in operations:
                await self.sleep(1)
                try:
                    imported = await operation.execute(SyncGroupCommand(group_id))
                    run.imported += int(imported)
                    run.skipped += int(not imported)
                except Exception as error:  # noqa: BLE001 -- isolate one group from the remaining batch
                    if len(run.errors) < 100:
                        run.errors.append(
                            f"{label} group={group_id}: {type(error).__name__}"
                        )
