import argparse
import logging

from app.core.database import engine
from app.domains.content.events.service import TeamMatchEventSync
from sqlmodel import Session


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
    sync = TeamMatchEventSync()

    with Session(engine) as session:
        created, updated = sync.backfill(
            session,
            completed_only=args.completed_only,
        )
        session.commit()

    logger.info(
        "TeamMatch-Event-Backfill abgeschlossen: created=%s updated=%s",
        created,
        updated,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
