from zoneinfo import ZoneInfo

from app.core.content.articles.application.dto import (
    GeneratedMatchReport,
    MatchReportData,
)


class PlainTextMatchReportGenerator:
    """Deterministic plain text; no HTML, external calls, or invented match details."""

    def generate(self, data: MatchReportData) -> GeneratedMatchReport:
        match = data.match
        home, away = (
            (match.team_name, match.opponent_name)
            if match.is_home
            else (match.opponent_name, match.team_name)
        )
        own = str(match.score_ttc) if match.score_ttc is not None else "?"
        opponent = (
            str(match.score_opponent) if match.score_opponent is not None else "?"
        )
        score = f"{own}:{opponent}" if match.is_home else f"{opponent}:{own}"
        title = f"{home} – {away}: {score}"
        date = match.scheduled_at.astimezone(ZoneInfo("Europe/Berlin")).strftime(
            "%d.%m.%Y, %H:%M Uhr"
        )
        teaser = f"Am {date} spielte {home} gegen {away}. Ergebnis: {score}."
        lines = [title, "", teaser]
        venue = ", ".join(
            part
            for part in (match.venue_name, match.venue_street, match.venue_city)
            if part
        )
        if venue:
            lines.extend([f"Spielort: {venue}"])
        if match.lineup:
            lines.extend(["", f"Aufstellung {match.team_name}:"])
            lines.extend(
                f"- {entry.player.first_name} {entry.player.last_name}"
                for entry in match.lineup
            )
        lines.extend(
            [
                "",
                "Einzel und Doppel",
                f"Alle folgenden Satzstände aus Sicht von {match.team_name}.",
            ]
        )
        for game in sorted(match.games, key=lambda item: item.sequence):
            players = (
                " / ".join(f"{p.first_name} {p.last_name}" for p in game.players)
                or "Aufstellung nicht verfügbar"
            )
            opponents = (
                " / ".join(dict.fromkeys(game.opponent_names))
                or "Gegner nicht verfügbar"
            )
            kind = {
                "single": "Einzel",
                "double": "Doppel",
                "doubles": "Doppel",
                "SINGLE": "Einzel",
                "DOUBLE": "Doppel",
            }.get(game.game_type, game.game_type)
            sets = ", ".join(
                f"{s.points_ttc}:{s.points_opponent}"
                for s in sorted(game.sets, key=lambda item: item.set_number)
            )
            lines.extend(
                [
                    "",
                    f"{game.sequence}. {kind}: {players} – {opponents}",
                    f"Sätze: {sets}" if sets else "Keine Satzergebnisse vorhanden.",
                ]
            )
        if not match.games:
            lines.append("Keine Einzel- oder Doppelergebnisse vorhanden.")
        return GeneratedMatchReport(
            title, teaser, "\n".join(lines), "match-data-template-v1"
        )
