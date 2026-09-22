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
über `build_assign_player_to_team().execute(command)` ausgeführt. Der ADMIN-Endpunkt
`PUT /api/competition/teams/{team_id}/lineup/{player_id}` verwendet die automatische
Zuordnung ohne manuelle Position und ohne Statusänderungsoption.

Ohne Position werden ausschließlich Meldungen derselben Saison/Halbserie und
Kategorie der Zielmannschaft verwendet (Herren, J15, J19 jeweils getrennt).
Die Reihenfolge ergibt sich aus `Team.team_number` und dem numerischen
`TeamMembership.rank` (in der Datenbank z. B. "2", nicht "1.2"). Alle internen
Positionen werden lückenlos ab 1 vergeben. Fehlende Kategorie, fehlende/ungültige
oder widersprüchliche Ränge verhindern die automatische Zuordnung.
Zusätzlich muss die Meldungsmannschaft mindestens die Nummer der Zielmannschaft
haben: In Mannschaft 3 sind 3.x, 4.x usw. möglich, aber keine 2.x. Dies ist eine
einfache interne Auswahlregel und keine vollständige Prüfung aller Spielordnungen.
Sperrvermerke und weitere Sonderfälle sind noch nicht berücksichtigt.

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
Zuordnung und Entfernen sperren die Mannschaft während der Transaktion mit
`SELECT FOR UPDATE`, damit parallele interne Änderungen keine Spieler verlieren.

`GetTeamCandidates` liest über den Competition-Reader ausschließlich Meldedaten
derselben Saison/Halbserie und Kategorie. Die gemeinsame Domainfunktion
`eligible_registration` bestimmt die erlaubten Spieler sowohl für Auswahl als auch
automatisches Schreiben. Bereits zugeordnete Spieler werden ausgeblendet; fehlende,
ungültige oder mehrdeutige Ränge und doppelt belegte Positionen werden ausgeschlossen.
Sortierung erfolgt numerisch nach Mannschaft und Rang, z. B. 3.2 vor 3.10.
Spielernamen liefert der bestehende gebündelte Members-Spieleradapter.
`GET /api/competition/teams/{team_id}/candidates` ist ADMIN-geschützt.


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
Die Abfrage löst keinen Sync aus; HTTP-Zugriff siehe unten.

Lesende Usecases (`ListTeams`, `GetSchedule`) liegen in `application/queries.py`.
`AssignPlayerToTeam` bleibt in `application/commands.py`.


`GetTeamStandings.execute(GetTeamStandingsQuery(team_id))` liefert die gespeicherte
Tabelle der Ligagruppe dieser Mannschaft als Liste von `StandingSummary`.
Sortiert wird nach Platzierung und Tabellenzeilen-ID. `is_selected_team` markiert
die gewählte Mannschaft. Das DTO enthält Begegnungs-, Punkte-, Spiel-, Satz- und
Ballstatistiken. Unbekannte Mannschaften oder fehlende Tabellen liefern `[]`.
Bootstrap bietet `build_get_team_standings()`. Die Abfrage ist rein lesend,
ohne myTT-Sync; HTTP-Zugriff siehe unten.


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
Bootstrap: `build_get_match_details()`. Kein Live-Sync; HTTP-Zugriff siehe unten.


`GetTeamLineup.execute(GetTeamLineupQuery(team_id))` liest ausschließlich die interne
Aufstellung aus `TeamAssignment`, nicht die externe Meldung oder eine Spielaufstellung.
Der Usecase ergänzt pro Spieler `media_id` über den öffentlichen Members-Vertrag
`GetPlayerImages`. Die Saison und Halbserie der Mannschaft bestimmen die historische
Bildauswahl; fehlende Bilder ergeben `None`. Der ADMIN-Endpunkt liefert diese
optionale Medien-ID mit. Die CMS-Mannschaftsseite bietet eine Saison-/Halbserienwahl
und eine Zeilenliste mit Links zur Detailseite `/admin/teams/:teamId`. Dort erscheint
die interne Aufstellung samt geschützten Bildvorschauen. Der Queryparameter `season`
erhält den Saisonfilter beim Navigieren und Neuladen. Seitenzugriff
und Menüeintrag sind entsprechend ebenfalls ADMIN vorbehalten. Schreibaktionen
zum Hinzufügen und Entfernen sind auf der Detailseite verfügbar. Der Button unter
der Aufstellung öffnet einen modalen Dialog. Die Suche filtert direkt sichtbare
Spielerzeilen mit Meldeposition, Name und Hinzufügen-Button, ohne Dropdown.
Der Dialog schließt nach erfolgreichem Speichern; Fehler erscheinen im Dialog.
Escape und Schließen führen zurück zum auslösenden Button, während des Speicherns
ist Schließen gesperrt.
Entfernen verlangt eine Bestätigung in der Zeile. Nach erfolgreichem Schreiben
wird die Aufstellung einschließlich historischer Bilder neu geladen.
Bildwechsel sind über den Bild-Button einer Spielerzeile verfügbar. Der ADMIN-Endpunkt
`PUT /api/competition/teams/{team_id}/lineup/{player_id}/image` übergibt die Zuordnung
an Members. Saison und Halbserie stammen serverseitig aus der Mannschaft; der
Aufstellungseintrag muss vorhanden sein. Details: [Spielerbilder](player-images.md).
`TeamLineup` enthält Mannschaftsname, Saison-ID, Kategorie und Spieler mit Namen,
Position und optionalem Status. Sortierung: Position aufsteigend, fehlende Positionen
zuletzt, bei Gleichstand Spieler-ID. Es wird nicht neu sortiert oder gespeichert.
Ohne Zuordnungen bleibt `players` leer; unbekannte Teams führen zu `TeamNotFoundError`.
Bootstrap: `build_get_team_lineup()`. Spielernamen kommen gebündelt über den bereits
vorhandenen Spieler-Reader. Keine Datenbankänderung; HTTP-Zugriff siehe unten.


`RemovePlayerFromTeam.execute(RemovePlayerFromTeamCommand(team_id, player_id))`
entfernt eine interne Zuordnung. `Team.remove_player` erhält die bestehende
Reihenfolge (Position, dann Spieler-ID; fehlende Positionen zuletzt) und vergibt
Positionen lückenlos ab 1. Es erfolgt kein Abgleich mit externen Meldungsrängen.
Statuswerte, Meldungen und Zuordnungen in anderen Mannschaften bleiben erhalten.
Fehlende Zuordnungen sind ein unveränderter Erfolg, unbekannte Mannschaften führen
zu `TeamNotFoundError`. Bootstrap: `build_remove_player_from_team()`.
Speichern und Entfernen erfolgen in einer Transaktion. Der ADMIN-Endpunkt
`DELETE /api/competition/teams/{team_id}/lineup/{player_id}` entfernt ausschließlich
die interne Zuordnung, keine Spieler, Meldungen oder Bildhistorien. PUT und DELETE
liefern 204, unbekannte Mannschaften 404; PUT liefert bei unbekannten Spielern 404
und bei verletzten Zuordnungsregeln 422. Keine Anmeldung ergibt 401, fehlende
ADMIN-Rolle 403. Die HTTP-Schnittstelle bietet keinen manuellen Positions-Bypass.


`ListSeasons.execute()` liefert alle gespeicherten Saisons/Halbserien als
`SeasonSummary` (ID, Startjahr, Endjahr, Halbserie). Neueste Saison zuerst,
innerhalb eines Jahresbereichs Rückrunde vor Vorrunde. Auch Saisons ohne
Mannschaften werden geliefert; eine leere Datenbank ergibt `[]`.
Ohne Eingabeparameter ist kein Query-DTO erforderlich. Bootstrap:
`build_list_seasons()`. Kein Sync; HTTP-Zugriff siehe unten.


## Lesende HTTP-Schnittstellen

Alle Endpunkte liegen unter `/api/competition`:

| GET-Pfad | Parameter | Zugriff |
| --- | --- | --- |
| `/seasons` | keine | öffentlich |
| `/teams` | `season_id`, optional `category` | öffentlich |
| `/schedule` | `date_from`, `date_to`, optional wiederholtes `team_ids`, `category` | öffentlich |
| `/teams/{team_id}/standings` | Mannschaft-ID | öffentlich |
| `/matches/{match_id}` | Begegnungs-ID | öffentlich |
| `/teams/{team_id}/lineup` | Mannschaft-ID | ADMIN |

Beispiel: `/api/competition/schedule?date_from=2026-09-01&date_to=2026-09-30&team_ids=1&team_ids=2`.
Ohne `team_ids` werden alle Mannschaften berücksichtigt. IDs müssen positiv sein;
fehlende oder ungültige Parameter sowie umgekehrte Zeiträume ergeben 422.
Unbekannte Begegnungen und (bei berechtigtem Zugriff) unbekannte Mannschaften beim
Lineup ergeben 404. Andere Listenabfragen liefern bei fehlenden Treffern `[]`.
Die interne Aufstellung ist vorerst nur mit ADMIN-Rolle erreichbar (401 ohne Anmeldung,
403 ohne Rolle). Öffentliche Begegnungsdetails enthalten Spielernamen, keine privaten
Mitgliedsdaten. Die Router verwenden eigene Response-Modelle und Bootstrap-Dependencies.
Es erfolgen keine Sync-Aufrufe oder Schreiboperationen.
