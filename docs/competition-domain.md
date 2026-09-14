# Interne Competition-Modelle

Die bisherigen fachlichen Modelle gibt es nun in zwei getrennten Formen:
frameworkfreie Domain-Entities im Core und SQLModel-Tabellenklassen im
Persistenzadapter. Sie haben bewusst dieselben Namen und weitgehend dieselben
Felder. SQL-Typen, Fremdschlüssel, Indizes und Tabellenkonfiguration bleiben
ausschließlich beim Persistenzmodell.

## Dateien und Zusammengehörigkeit

| Domain-Datei unter `app/core/competition/domain` | Entities |
| --- | --- |
| `seasons.py` | `Season`, `SeasonKey`, `SeasonHalf` |
| `teams.py` | `Team`, `TeamMembership`, `TeamAssignment` |
| `matches.py` | `TeamMatch`, `Match`, `MatchLineup`, `MatchParticipant`, `SetResult`, `TeamMatchNotice`, `GameType`, `TeamMatchNoticeCode` |
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
- `TeamMatch.record_result(...)` übernimmt abgeschlossene Ergebnisse als
  Domainobjekte (`Match`, `MatchLineup`) und vereinsbezogene Punktestände.
  Die Methode kennt weder Import-DTOs noch die Datenquelle.
- Die Sync-Application übersetzt Spielplan- und Ergebnisdaten in `sync/mapping.py`.
  Sie ordnet Heim-/Auswärtswerte zu, baut Teilnehmer und Sätze auf und berücksichtigt
  Aufstellungsinformationen ungespielter Spiele. Spielplanänderungen bewahren Details.
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

`application/sync/imports.py` definiert die DTOs der Quell- und Reader-Ports. Es enthält keine
ORM-Klassen. Der bisherige SQL-Importadapter wurde durch `repository.py`
ersetzt; Importentscheidungen befinden sich nun in Application und Domain.

Tests prüfen die Regeln ohne SQL sowie vollständige Entity-Roundtrips,
Wiederholungsimporte, Erhalt vorhandener Detaildaten und Rollbacks. Read-Usecases
dürfen weiterhin optimierte DTO-Projektionen statt vollständiger Entities nutzen.


## Interne Mannschaftsaufstellung

`AssignPlayerToTeamCommand(team_id, player_id, status=None, position=None)` wird
über `build_assign_player_to_team().execute(command)` ausgeführt. HTTP ist geplant.

Ohne Position werden ausschließlich Meldungen derselben Saison/Halbserie und
Kategorie der Zielmannschaft verwendet (Herren, J15, J19 jeweils getrennt).
Die Reihenfolge ergibt sich aus `Team.team_number` und dem numerischen
`TeamMembership.rank` (in der Datenbank z. B. "2", nicht "1.2"). Alle internen
Positionen werden lückenlos ab 1 vergeben. Fehlende Kategorie, fehlende/ungültige
oder widersprüchliche Ränge verhindern die automatische Zuordnung.

Eine explizite Position erlaubt manuelles Einfügen oder Verschieben, auch ohne
Kategorie und Meldungsrang. Erlaubt sind 1 bis zur resultierenden Spielerzahl;
die übrigen Spieler werden verschoben. Vorhandene Positionen bestimmen ihre
Reihenfolge, bei Gleichstand die Spieler-ID; Einträge ohne Position folgen hinten.
Eine spätere automatische Zuordnung berechnet die gesamte Aufstellung neu und
ersetzt damit die manuelle Reihenfolge. Importierte Meldungsänderungen allein
sortieren die interne Aufstellung noch nicht neu.

`AssignmentStatus.SUBSTITUTE` speichert "Ersatzspieler", `None` eine reguläre
Zuordnung. Erneutes Zuordnen aktualisiert bzw. löscht den Status. Dieser beeinflusst
die Reihenfolge nicht. Externe Meldungen bleiben unverändert. Die vorhandenen
Datenbankspalten reichen aus; es ist keine Migration nötig. Der PlayerLookup
verwendet eine eigene Lesesession, die Unit of Work speichert die Aufstellung atomar.


Allgemeine Usecases und Verträge liegen direkt in `application/`:
`commands.py`, `dto.py`, `ports.py`, `errors.py`. Die vollständige Sync-Anwendung
liegt unter `application/sync/`: `commands.py`, `batches.py`, `backfill.py`,
`queries.py`, `mapping.py`, `dto.py`, `imports.py`, `ports.py`, `errors.py`.
Der Meldungsbericht gehört zur Sync-Diagnose. Beide Bereiche definieren eigene Repository- und Unit-of-Work-Ports.
Der allgemeine Repository-Port enthält `get_team`, `registration_for_category`
und `save_team`; der Sync-Port enthält die Zugriffe für Synchronisierungen.
`SyncUnitOfWork` verwendet den Sync-Repository-Port sowie Importspieler und Event-Abgleich.
Beide Verträge werden weiterhin von denselben SQL-Adaptern erfüllt.
Die allgemeine Application importiert keine Sync-Typen.

Die Domain importiert keine Application-DTOs. `original_schedule` bleibt als
Terminregel in `domain/matches.py`; der Abgleich importierter Mannschaftsmeldungen
liegt in `application/sync/mapping.py`. Vorhandene externe ID-Felder und
die Importmarkierung bleiben aus Kompatibilitätsgründen erhalten. Ihre Auslagerung
ist nicht Teil dieser Trennung; Datenbankschema und gespeicherte Werte ändern sich nicht.


Die Verdrahtung ist getrennt: `bootstrap/competition.py` baut allgemeine Usecases
auf; `bootstrap/competition_sync.py` baut Sync-Usecases, myTT-Client, Backfill
und Meldungsbericht auf. Die Factory-Funktionsnamen bleiben unverändert.


`GetSchedule.execute(GetScheduleQuery(date_from, date_to, team_ids=None, category=None))`
liefert Begegnungen als `ScheduledMatchSummary`, sortiert nach Termin und ID.
Beide Tage sind einschließlich in Europe/Berlin; die SQL-Abfrage verwendet UTC-Grenzen
vom Tagesanfang bis ausschließlich zum folgenden Tagesanfang (auch bei Zeitumstellung).
Ein umgekehrter Zeitraum wird abgelehnt. Ohne Teams (`None` oder leeres Tupel) werden
alle Teams berücksichtigt, sonst nur die angegebenen IDs. Eine Mannschaft-ID gehört
zu einer Saison/Halbserie; die Abfrage benötigt keinen separaten Saisonfilter.
Kategorie und Teams werden als gemeinsame Einschränkungen behandelt. Ohne Treffer
wird eine leere Liste geliefert. Bootstrap bietet `build_get_schedule()`.
HTTP ist noch nicht implementiert; die Abfrage löst keinen Sync aus.

Lesende Usecases (`ListTeams`, `GetSchedule`) liegen in `application/queries.py`.
`AssignPlayerToTeam` bleibt in `application/commands.py`.


`GetTeamStandings.execute(GetTeamStandingsQuery(team_id))` liefert die gespeicherte
Tabelle der Ligagruppe dieser Mannschaft als Liste von `StandingSummary`.
Sortiert wird nach Platzierung und Tabellenzeilen-ID. `is_selected_team` markiert
die gewählte Mannschaft. Das DTO enthält Begegnungs-, Punkte-, Spiel-, Satz- und
Ballstatistiken. Unbekannte Mannschaften oder fehlende Tabellen liefern `[]`.
Bootstrap bietet `build_get_team_standings()`. Die Abfrage ist rein lesend,
ohne myTT-Sync; HTTP ist noch nicht implementiert.


`GetMatchDetails.execute(GetMatchDetailsQuery(team_match_id))` liefert verschachtelte
Begegnungsdetails: Grunddaten, Spielort, Hinweise, tatsächliche Aufstellung sowie
Einzel/Doppel mit Spielern, Gegnernamen und geordneten Satzergebnissen. Punkte
bleiben vereinsbezogen (`points_ttc`/`points_opponent`), auch bei Auswärtsspielen.
Gegnernamen werden als gespeicherte Texte übernommen; bei Doppeln kann ein Text
beide Namen enthalten. Interne `TeamAssignment`-Planungen werden nicht verwendet.
Unbekannte IDs führen zu `MatchNotFoundError`. Ohne Importmarkierung bleiben
Detail-Listen leer und `details_available=False`. Der Mitgliederadapter liefert
über `MatchPlayerReader` nur Spieler-ID und Namen, keine privaten Kontaktdaten.
Abfragen erfolgen gebündelt, maximal sieben SELECTs statt Abfragen pro Einzelspiel.
Bootstrap: `build_get_match_details()`. Kein Live-Sync, kein HTTP-Endpunkt.
