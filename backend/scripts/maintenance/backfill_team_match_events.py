import argparse
import logging

from app.bootstrap.competition_sync import build_backfill_match_events
from app.core.competition.application.sync.dto import BackfillMatchEventsCommand

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erzeugt oder aktualisiert Events aus vorhandenen TeamMatches."
    )
    parser.add_argument(
        "--completed-only",
        action="store_true",
        help="Nur bereits abgeschlossene Mannschaftsspiele verarbeiten.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    created, updated = build_backfill_match_events().execute(
        BackfillMatchEventsCommand(completed_only=args.completed_only)
    )

    logger.info(
        "TeamMatch-Event-Backfill abgeschlossen: created=%s updated=%s",
        created,
        updated,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
