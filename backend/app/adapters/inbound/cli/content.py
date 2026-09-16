"""Trusted local operator commands; no HTTP or web UI endpoints."""

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from app.adapters.outbound.persistence.database import engine
from app.bootstrap.articles import (
    build_create_match_report_draft,
    build_edit_article_draft,
)
from app.bootstrap.content_worker import build_content_worker
from app.bootstrap.logging import configure_logging
from app.bootstrap.messaging import (
    build_get_outbox_status,
    build_process_outbox,
    build_retry_outbox_message,
)
from app.bootstrap.settings import settings
from app.core.content.articles.application.dto import (
    CreateMatchReportDraftCommand,
    EditArticleDraftCommand,
)
from app.core.messaging.application.dto import (
    GetOutboxStatusQuery,
    ProcessOutboxCommand,
    RetryOutboxMessageCommand,
)
from sqlmodel import Session


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Berichtsentwürfe und Outbox-Verarbeitung"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser(
        "generate-report", help="Entwurf für ein gespeichertes Spiel erzeugen"
    )
    report.add_argument("match_id", type=int)
    report.add_argument(
        "--author-id", type=int, help="ADMIN/EDITOR; ohne Angabe Systemautor"
    )
    edit = commands.add_parser(
        "edit-draft", help="Entwurf bearbeiten und Autor übernehmen"
    )
    edit.add_argument("article_id", type=int)
    edit.add_argument("--author-id", type=int, required=True)
    edit.add_argument("--title", required=True)
    edit.add_argument("--teaser", required=True)
    edit.add_argument("--content-file", type=Path, required=True)
    process = commands.add_parser(
        "process-outbox", help="Fällige Nachrichten einmal verarbeiten"
    )
    process.add_argument("--limit", type=int, default=100)
    status = commands.add_parser("outbox-status", help="Bearbeitungsstatus anzeigen")
    status.add_argument("--limit", type=int, default=20)
    retry = commands.add_parser(
        "retry-message", help="Fehlgeschlagene Nachricht erneut freigeben"
    )
    retry.add_argument("event_id", type=UUID)
    worker = commands.add_parser(
        "worker", help="Regelmäßigen Sync und Outbox-Verarbeitung starten"
    )
    worker.add_argument(
        "--once", action="store_true", help="Einmal Sync und Verarbeitung ausführen"
    )
    args = parser.parse_args(argv)
    configure_logging(
        log_level=settings.log_level,
        mytt_log_level=settings.mytt_log_level,
        log_to_file=settings.log_to_file,
        log_directory=settings.log_directory,
        log_max_bytes=settings.log_max_bytes,
        log_backup_count=settings.log_backup_count,
    )
    if args.command == "worker":
        worker = build_content_worker()
        try:
            result = asyncio.run(worker.once() if args.once else worker.run())
        except KeyboardInterrupt:
            return
        if result is False:
            raise SystemExit(1)
    elif args.command == "generate-report":
        with Session(engine) as session:
            result = build_create_match_report_draft(session).execute(
                CreateMatchReportDraftCommand(args.match_id, author_id=args.author_id)
            )
            print(json.dumps(asdict(result)))
    elif args.command == "edit-draft":
        with Session(engine) as session:
            build_edit_article_draft(session).execute(
                EditArticleDraftCommand(
                    args.article_id,
                    args.author_id,
                    args.title,
                    args.teaser,
                    args.content_file.read_text(encoding="utf-8"),
                )
            )
        print("Entwurf gespeichert.")
    elif args.command == "process-outbox":
        result = build_process_outbox().execute(ProcessOutboxCommand(args.limit))
        print(json.dumps(asdict(result)))
        if result.failed:
            raise SystemExit(1)
    elif args.command == "outbox-status":
        print(
            json.dumps(
                build_get_outbox_status().execute(GetOutboxStatusQuery(args.limit)),
                default=str,
                indent=2,
            )
        )
    elif args.command == "retry-message":
        build_retry_outbox_message().execute(RetryOutboxMessageCommand(args.event_id))
        print("Nachricht zur erneuten Verarbeitung freigegeben.")
