"""Argument parsing only; historical and current imports share application use cases."""

import argparse

from app.bootstrap.competition import build_competition
from app.bootstrap.logging import configure_logging
from app.bootstrap.settings import settings
from app.core.competition.application.dto import (
    SyncCurrentCommand,
    SyncExternalMeetingCommand,
    SyncHistoryCommand,
    SyncScheduleCommand,
)
from app.core.competition.domain.imports import SeasonHalf, SeasonKey


async def main(kind: str, argv=None):
    parser = argparse.ArgumentParser(description="myTischtennis-Import")
    if kind == "current":
        parser.add_argument(
            "sync_type", choices=["schedule", "meetings", "tables", "registrations"]
        )
    elif kind == "schedule":
        parser.add_argument("start_year", type=int)
        parser.add_argument("end_year", type=int)
        parser.add_argument("half", type=SeasonHalf, choices=list(SeasonHalf))
    elif kind == "registrations":
        parser.add_argument("start_year", type=int)
        parser.add_argument("end_year", type=int)
    elif kind == "tables":
        parser.add_argument("--include-existing", action="store_true")
    elif kind == "meeting":
        parser.add_argument("meeting_id", type=int, help="myTischtennis-Begegnungs-ID")
    elif kind != "meetings":
        raise ValueError("Unbekannter CLI-Einstieg.")
    args = parser.parse_args(argv)
    if kind == "registrations" and args.end_year < args.start_year:
        parser.error("end_year darf nicht vor start_year liegen")
    configure_logging(
        log_level=settings.log_level,
        mytt_log_level=settings.mytt_log_level,
        log_to_file=settings.log_to_file,
        log_directory=settings.log_directory,
        log_max_bytes=settings.log_max_bytes,
        log_backup_count=settings.log_backup_count,
    )
    usecases = build_competition()
    if kind == "current":
        result = await usecases.current.execute(SyncCurrentCommand(args.sync_type))
    elif kind == "schedule":
        result = await usecases.schedule.execute(
            SyncScheduleCommand(SeasonKey(args.start_year, args.end_year, args.half))
        )
    elif kind == "meeting":
        result = await usecases.external_meeting.execute(
            SyncExternalMeetingCommand(args.meeting_id)
        )
    else:
        result = await usecases.history.execute(
            SyncHistoryCommand(
                kind,
                getattr(args, "start_year", None),
                getattr(args, "end_year", None),
                not getattr(args, "include_existing", False),
            )
        )
    if isinstance(result, bool):
        print("Import abgeschlossen." if result else "Import übersprungen.")
    else:
        print(
            f"Importiert: {result.imported}; übersprungen: {result.skipped}; fehlgeschlagen: {len(result.failed)}"
        )
        if result.failed:
            print("Fehlgeschlagene IDs:", ", ".join(map(str, result.failed)))
    if getattr(result, "failed", None):
        raise SystemExit(1)
