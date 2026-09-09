# Interne Competition-Modelle

Die bisherigen fachlichen Modelle gibt es nun in zwei getrennten Formen:
frameworkfreie Domain-Entities im Core und SQLModel-Tabellenklassen im
Persistenzadapter. Sie haben bewusst dieselben Namen und weitgehend dieselben
Felder. SQL-Typen, Fremdschlüssel, Indizes und Tabellenkonfiguration bleiben
ausschließlich beim Persistenzmodell.

## Dateien und Zusammengehörigkeit

| Domain-Datei unter `app/core/competition/domain` | Entities |
| --- | --- |
| `seasons.py` | `Season` |
| `teams.py` | `Team`, `TeamMembership`, `TeamAssignment` |
| `matches.py` | `TeamMatch`, `Match`, `MatchLineup`, `MatchParticipant`, `SetResult`, `TeamMatchNotice` |
| `leagues.py` | `LeagueGroup`, `LeagueTableEntry` |

Die zugehörigen SQLModel-Dateien liegen unter
`app/adapters/outbound/persistence/competition` und tragen dieselben Dateinamen.
In Application-Code wird immer aus der Domain importiert. Der SQL-Adapter
verwendet getrennte Modulnamen, um Domain- und Persistenzklassen zu unterscheiden.

`TeamMatch` fasst `notices`, `lineup` und `matches` zusammen. Ein `Match`
enthält `participants` und `sets`. `Team` enthält `memberships` und
`assignments`; `LeagueGroup` enthält `table`. Andere Gruppen werden über ihre
IDs referenziert, beispielsweise `team_id` und `season_id`. Dadurch muss nicht
die gesamte Saison als ein einziger Objektbaum geladen werden.

Neue Entities besitzen bis zur Speicherung keine Datenbank-ID. Repositories
tragen erzeugte IDs ein; bei untergeordneten Entities setzen sie außerdem die
Parent-ID. Die vorhandenen Fremdschlüssel und Tabellen bleiben unverändert.

## Fachliches Verhalten

- `TeamMatch.reschedule(...)` bewahrt den ersten ursprünglichen Termin.
  Ein ausdrücklich übergebener ursprünglicher Termin hat Vorrang.
- `TeamMatch.update_schedule(...)` übernimmt Spielplan-Metadaten und Hinweise,
  erhält aber importierte Spiele, Aufstellung und Importmarkierung.
- `TeamMatch.import_details(...)` übernimmt nur abgeschlossene Begegnungen,
  bildet Heim-/Auswärtsergebnisse ab und erstellt Aufstellung, Spiele,
  Teilnehmer und Sätze. Ungespielte Spiele können Aufstellungsinformationen
  liefern, werden aber nicht als gespielte Matches übernommen.
- `Team.replace_registration(...)` ersetzt die Mannschaftsmeldung und erhält
  die separate Aufstellung (`assignments`).
- `LeagueGroup.replace_table(...)` übernimmt Tabellen-Entities und verhindert
  doppelte Mannschaften. Der Usecase bewahrt weiterhin den vorhandenen Stand,
  wenn die externe Quelle keine Tabelle liefert.
- `Season` prüft den Jahresbereich und stellt seinen `SeasonKey` bereit.

## Beispiel

```python
from datetime import datetime, timezone

with uow:
    match = uow.repository.get_team_match(match_id)
    if match is None:
        raise ValueError("Begegnung nicht gefunden.")
    match.reschedule(datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc))
    uow.repository.save_team_match(match)
    uow.commit()
```

Die Import-Usecases verwenden genau diese Trennung: Quelle abrufen, Entities
laden oder anlegen, fachliche Änderungen ausführen, Entities speichern und
die Transaktion committen. Spieleridentitäten werden über den bestehenden
Members-Port aufgelöst und als IDs an die Domain übergeben.

`domain/imports.py` bleibt das Übergabeformat der Datenquelle. Es enthält keine
ORM-Klassen. Der bisherige SQL-Importadapter wurde durch `repository.py`
ersetzt; Importentscheidungen befinden sich nun in Application und Domain.

Tests prüfen die Regeln ohne SQL sowie vollständige Entity-Roundtrips,
Wiederholungsimporte, Erhalt vorhandener Detaildaten und Rollbacks. Read-Usecases
dürfen weiterhin optimierte DTO-Projektionen statt vollständiger Entities nutzen.
