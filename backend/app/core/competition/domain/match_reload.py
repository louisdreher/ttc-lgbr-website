from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReloadTarget:
    id: int
    is_completed: bool
    details_imported_at: datetime | None
    external_id: int | None

    def blocked_reason(self) -> str | None:
        if self.details_imported_at is not None:
            return "Die Spieldetails wurden bereits erfolgreich importiert."
        if not self.is_completed:
            return "Das Spiel ist noch nicht als abgeschlossen gespeichert."
        if self.external_id is None:
            return "Für dieses Spiel fehlt die externe myTischtennis-Spiel-ID."
        return None


@dataclass
class MatchReload:
    team_match_id: int
    requested_at: datetime
    status: str = "requested"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in {"requested", "running"}

    def request(self, now: datetime) -> None:
        if not self.is_open:
            self.status, self.requested_at = "requested", now
            self.started_at = self.finished_at = self.last_error = None

    def start(self, now: datetime) -> None:
        self.status, self.started_at = "running", now
        self.finished_at = self.last_error = None

    def finish(self, now: datetime, error: str | None = None) -> None:
        self.status = "failed" if error else "succeeded"
        self.finished_at, self.last_error = now, error

    def recover(self) -> None:
        if self.status == "running":
            self.status = "requested"
            self.last_error = "Unterbrochener Auftrag wird erneut übernommen."
