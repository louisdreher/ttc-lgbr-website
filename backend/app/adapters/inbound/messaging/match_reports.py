from app.core.competition.public import ImportOrigin, TeamMatchResultsImported
from app.core.content.articles.application.dto import CreateMatchReportDraftCommand
from app.core.messaging.application.dto import Delivery, PermanentDeliveryError

MATCH_RESULTS_IMPORTED = "competition.team_match_results_imported.v1"


class MatchResultsImportedHandler:
    def __init__(self, session_factory, report_factory):
        self.session_factory, self.report_factory = session_factory, report_factory

    def handle(self, delivery: Delivery) -> None:
        if delivery.event_type != MATCH_RESULTS_IMPORTED:
            raise PermanentDeliveryError(
                "Unbekannter Nachrichtentyp oder unbekannte Version."
            )
        payload = delivery.payload
        if (
            not isinstance(payload, dict)
            or type(payload.get("team_match_id")) is not int
            or payload["team_match_id"] <= 0
        ):
            raise PermanentDeliveryError("Ungültige Spiel-ID in der Nachricht.")
        try:
            origin = ImportOrigin(payload.get("import_origin"))
        except (ValueError, TypeError) as error:
            raise PermanentDeliveryError("Ungültige Importherkunft.") from error
        event = TeamMatchResultsImported(
            delivery.event_id, payload["team_match_id"], delivery.occurred_at, origin
        )
        if event.import_origin != ImportOrigin.CURRENT:
            return
        with self.session_factory() as session:
            self.report_factory(session).execute(
                CreateMatchReportDraftCommand(
                    event.team_match_id,
                    require_report_expected=True,
                )
            )
