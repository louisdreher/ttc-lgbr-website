import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime

from app.core.competition.application.dto import (
    ImportSummary,
    SyncCurrentCommand,
    SyncGroupCommand,
    SyncHistoryCommand,
    SyncMeetingCommand,
    SyncScheduleCommand,
)
from app.core.competition.application.ports import CompetitionReader, SourceError
from app.core.competition.application.usecases.sync.commands import (
    SyncMeeting,
    SyncRegistrations,
    SyncSchedule,
    SyncStandings,
)
from app.core.competition.domain.seasons import SeasonHalf, SeasonKey

logger = logging.getLogger(__name__)


class ImportBatch:
    def __init__(self, sleep: Callable[[float], Awaitable[None]]):
        self.sleep = sleep

    async def run(
        self,
        ids: list[int],
        operation,
        *,
        attempts=1,
        delay=1.0,
        retry_delay=3.0,
        backoff="constant",
        retry_validation=False,
    ) -> ImportSummary:
        summary = ImportSummary()
        for index, item_id in enumerate(ids):
            for attempt in range(attempts):
                try:
                    if await operation(item_id):
                        summary.imported += 1
                    else:
                        summary.skipped += 1
                    break
                except Exception as error:
                    retryable = (
                        isinstance(error, SourceError) and error.retryable
                    ) or (
                        retry_validation
                        and isinstance(error, (RuntimeError, ValueError))
                    )
                    if not retryable or attempt + 1 == attempts:
                        summary.failed.append(item_id)
                        logger.exception("Import fehlgeschlagen: id=%s", item_id)
                        break
                    factor = (
                        2**attempt
                        if backoff == "exponential"
                        else attempt + 1
                        if backoff == "linear"
                        else 1
                    )
                    logger.warning(
                        "Import wird erneut versucht: id=%s attempt=%s",
                        item_id,
                        attempt + 1,
                    )
                    await self.sleep(retry_delay * factor)
            if index + 1 < len(ids):
                await self.sleep(delay)
        logger.info(
            "Import abgeschlossen: imported=%s skipped=%s failed=%s",
            summary.imported,
            summary.skipped,
            summary.failed,
        )
        return summary


class SyncCurrent:
    def __init__(
        self,
        schedule: SyncSchedule,
        meetings: SyncMeeting,
        registrations: SyncRegistrations,
        standings: SyncStandings,
        reader: CompetitionReader,
        batch: ImportBatch,
        today: Callable[[], date],
    ):
        self.schedule, self.meetings, self.registrations, self.standings = (
            schedule,
            meetings,
            registrations,
            standings,
        )
        self.reader, self.batch, self.today = reader, batch, today

    async def execute(self, command: SyncCurrentCommand) -> ImportSummary:
        if command.kind not in {"schedule", "meetings", "tables", "registrations"}:
            raise ValueError("Unbekannter Importtyp.")
        season = SeasonKey.current(self.today())
        imported = await self.schedule.execute(SyncScheduleCommand(season))
        if command.kind == "schedule":
            return ImportSummary(imported=int(imported), skipped=int(not imported))
        season_id = self.reader.season_id(season)
        if season_id is None:
            raise ValueError("Aktuelle Halbserie ist nicht in der Datenbank vorhanden.")
        if command.kind == "meetings":
            return await self.batch.run(
                self.reader.pending_match_ids(season_id=season_id),
                lambda match_id: self.meetings.execute(SyncMeetingCommand(match_id)),
            )
        operation = (
            self.registrations if command.kind == "registrations" else self.standings
        )
        return await self.batch.run(
            self.reader.group_ids(season_id),
            lambda group_id: operation.execute(SyncGroupCommand(group_id)),
            attempts=3 if command.kind == "registrations" else 1,
        )


class SyncHistory:
    def __init__(
        self,
        meetings: SyncMeeting,
        registrations: SyncRegistrations,
        standings: SyncStandings,
        reader: CompetitionReader,
        batch: ImportBatch,
        clock: Callable[[], datetime],
    ):
        self.meetings, self.registrations, self.standings = (
            meetings,
            registrations,
            standings,
        )
        self.reader, self.batch, self.clock = reader, batch, clock

    async def execute(self, command: SyncHistoryCommand) -> ImportSummary:
        if command.kind == "meetings":
            return await self.batch.run(
                self.reader.pending_match_ids(before=self.clock()),
                lambda match_id: self.meetings.execute(SyncMeetingCommand(match_id)),
                attempts=3,
                delay=1.5,
                retry_delay=5,
                backoff="exponential",
                retry_validation=True,
            )
        if command.kind == "tables":
            return await self.batch.run(
                self.reader.group_ids(with_team=True),
                lambda group_id: self.standings.execute(
                    SyncGroupCommand(group_id, command.skip_existing)
                ),
                attempts=3,
                delay=1.5,
                retry_delay=5,
                backoff="linear",
            )
        if command.kind != "registrations":
            raise ValueError("Unbekannter historischer Importtyp.")
        if (
            command.start_year is None
            or command.end_year is None
            or command.end_year < command.start_year
        ):
            raise ValueError("Gültiger Kalenderjahresbereich erforderlich.")
        group_ids = []
        for year in range(command.start_year, command.end_year + 1):
            for season in (
                SeasonKey(year - 1, year, SeasonHalf.RR),
                SeasonKey(year, year + 1, SeasonHalf.VR),
            ):
                season_id = self.reader.season_id(season)
                if season_id is not None:
                    group_ids.extend(self.reader.group_ids(season_id))
        return await self.batch.run(
            group_ids,
            lambda group_id: self.registrations.execute(SyncGroupCommand(group_id)),
            attempts=2,
            retry_delay=2,
            delay=1,
        )
