# myTischtennis: Competition-Imports mit Ports und Adaptern

Die Synchronisierung gehört fachlich zur Competition-Komponente. myTischtennis
ist ihre externe Datenquelle und wird über einen ausgehenden Port angesprochen.
Aktuelle und historische Imports verwenden dieselben Usecases.

## Aufbau

```text
scripts/mytt/*                          bestehende Startbefehle
    ↓
adapters/inbound/cli/competition.py     Argumente und Konsolenausgabe
    ↓
core/competition/application/           execute(command), Ablauf und Transaktion
    ├── CompetitionSource              Port für externe Wettbewerbsdaten
    │       ↑
    │   adapters/outbound/mytischtennis/
    │       source.py                  Validierung und Übersetzung
    │       client.py                  HTTP, URLs und myTT-Parameter
    └── CompetitionUnitOfWork           Transaktionsport
            ↑
        adapters/outbound/persistence/competition/
            repository.py              Domain-Entities ↔ Tabellenzeilen
            reader.py                  Auswahl und Referenzen
            unit_of_work.py            Session, Commit und Rollback
```

`app/bootstrap/competition.py` setzt die konkreten Implementierungen zusammen.
Settings, Datenbank-Engine, HTTP-Client und Uhr gelangen dadurch nicht in den Core.
Der Client kennt keine Datenbank; die Persistenzadapter führen keine API-Abfragen aus.

## Usecases und Domain

- `SyncSchedule.execute(SyncScheduleCommand(...))` übernimmt eine Halbserie
  und synchronisiert die abgeleiteten Events in derselben Transaktion.
- `SyncMeeting.execute(SyncMeetingCommand(...))` importiert abgeschlossene
  Begegnungsdetails. Bereits importierte Details werden ohne `force=True`
  übersprungen. `SyncExternalMeeting` löst vorher eine externe Begegnungs-ID auf.
- `SyncRegistrations.execute(SyncGroupCommand(...))` ersetzt die Meldungen der
  zugeordneten eigenen Mannschaften.
- `SyncStandings.execute(SyncGroupCommand(...))` ersetzt einen Tabellenstand;
  `skip_existing` steuert das Überspringen vorhandener Tabellen.
- `SyncCurrent` aktualisiert zuerst den Spielplan und verarbeitet danach die
  ausgewählte Datenart der aktuellen Halbserie.
- `SyncHistory` wählt historische Begegnungen, Tabellen oder Mannschaftsmeldungen.
  Historische Spielpläne verwenden direkt `SyncSchedule`.

`application/imports.py` enthält normale Python-Dataclasses für Spielplan,
Begegnungsdetails, Spieler, Meldungen und Tabellenstände. Halbserien und
Terminregeln liegen in der Domain; Mannschaftszuordnung und Übersetzung in
Domainobjekte stehen in `application/usecases/sync/mapping.py`.
Die Datenquelle liefert diese Typen. Externe JSON-Feldnamen und HTTP-Fehler
werden im myTischtennis-Adapter übersetzt und verlassen diesen nicht.

Intern arbeiten die Usecases mit den Entities aus `domain/seasons.py`,
`domain/teams.py`, `domain/matches.py` und `domain/leagues.py`. Die bisherigen
Modellnamen und fachlichen Felder sind dort als frameworkfreie Dataclasses
vorhanden. Die Snapshots dienen der Übernahme externer Daten; sie ersetzen
nicht die internen Entities.

`CompetitionRepository` lädt und speichert diese Entities. Die Auflösung von
Spieleridentitäten liegt beim Application-Usecase über `uow.players`.
Der SQL-Adapter übersetzt Entity-Zustände in Tabellenzeilen und synchronisiert
untergeordnete Datensätze. Er entscheidet nicht, welche importierten Spiele
gespielt wurden oder wie eine Mannschaftsmeldung zugeordnet wird.
Es gibt keine allgemeine SQL-Schnittstelle im Port und keinen Command-Bus.
Siehe [Competition-Domain](competition-domain.md) für die konkreten Modelle.

## Transaktionen und Komponentengrenzen

Lesezugriffe für API-Referenzen schließen ihre Session vor dem HTTP-Aufruf.
Erst nach Abruf und Formatprüfung beginnt die Schreibtransaktion. Repositories
dürfen flushen, aber nicht committen. Das Commit liegt beim Usecase.

Eine Begegnung inklusive Aufstellung, Einzel-/Doppelspielen, Teilnehmern,
Satzergebnissen und Importmarkierung wird vollständig gespeichert oder
zurückgerollt. Bei einem erzwungenen Wiederholungsimport bleiben vorherige
Details erhalten, wenn das Ersetzen fehlschlägt. Dasselbe gilt für Meldungen
und Tabellenstände.

`CompetitionMatchEvents` implementiert den `MatchEvents`-Port und ruft den
öffentlichen Events-Usecase mit `SyncMatchEventCommand` auf. Bootstrap verbindet
beide Komponenten mit derselben SQL-Session. Der vorhandene separate
Event-Backfill bleibt über `BackfillMatchEvents.execute(command)` verfügbar;
auch sein CLI-Skript enthält keine SQL-Abfragen mehr.

Spieleridentitäten werden über `ImportedPlayers` aufgelöst. Der Adapter
`persistence/members/imported_players.py` verbindet diesen expliziten Vertrag
mit den bestehenden Members-Tabellen. Widersprüchliche Spieler-IDs brechen die
Transaktion ab. Der bekannte myTT-Platzhalter für abwesende Spieler bleibt
unterstützt.

Die Competition-ORM-Modelle liegen unter `persistence/competition` in
`seasons.py`, `teams.py`, `matches.py` und `leagues.py`; Members verwendet
`persistence/members/models.py`. Die Halbserie und Spiel-/Hinweistypen sind
frameworkfreie Domain-Enums. Application und Domain importieren keine ORM-Modelle.
Für noch nicht vorhandene Verwaltungsfunktionen wurden keine zusätzlichen
Domain-Aggregate oder leeren Usecases angelegt.

## Wiederholungen und bewusst korrigiertes Verhalten

Der Core erhält `SourceError` mit einer Angabe, ob ein Fehler temporär ist.
Verbindungsfehler, ungültiges JSON, HTTP 403/408/429 und Serverfehler können
wiederholt werden. Wartezeiten werden injiziert; Tests schlafen nicht real.
Aktuelle Mannschaftsmeldungen verwenden bis zu drei Versuche. Historische
Meldungen verwenden zwei, Tabellen und Begegnungen drei Versuche. Historische
Begegnungen behalten ihre breitere Wiederholung bei Importfehlern.

Folgende Fehler wurden beim Umbau korrigiert:

- Eine leere externe Tabelle ersetzt keine vorhandene Tabelle mehr.
- Eine eigene Meldung mit fehlender Spieler-ID wird vollständig abgewiesen,
  bevor bestehende Zuordnungen ersetzt werden. Der vorherige Fehlerpfad
  verwendete eine undefinierte Variable.
- HTTP 429 wird als temporärer Quellfehler behandelt, statt durch einen
  allgemeinen RuntimeError an der vorgesehenen Wiederholung vorbeizulaufen.
- Batch-Fehler werden im Ergebnis aufgeführt; die CLI beendet sich dann mit
  Exitcode 1 und meldet keinen vollständigen Erfolg.

Pokal, Relegation und unbekannte Wettbewerbsarten bleiben vom Spielplanimport
ausgeschlossen. Es wurde kein Scheduler eingeführt.

## Start und Prüfung

Die bisherigen Modulbefehle und Parameter bleiben bestehen, beispielsweise:

```powershell
python -m scripts.mytt.run_current_sync meetings
python -m scripts.mytt.history.import_schedule 2018 2019 vr
python -m scripts.mytt.history.import_registrations 2009 2012
python -m scripts.mytt.history.import_meetings
python -m scripts.mytt.history.import_league_tables --include-existing
```

Diese Befehle führen echte Imports aus. Für eine reine Parameteranzeige dient
`--help`. Diagnose-Probes verwenden weiterhin den HTTP-Client direkt, weil sie
absichtlich die unverarbeiteten API-Antworten untersuchen. Der Datenbankbericht
`check_registrations` liest über einen Query-Usecase und einen SQL-Reader.

Automatisierte Tests verwenden Fake-Ports, gemockte API-Antworten und SQLite
mit aktivierten Fremdschlüsseln. Sie prüfen Wiederholbarkeit, Rollbacks,
Spielerauflösung, Heim-/Auswärtsperspektive, Fehlermeldungen, Batches und
CLI-Einstiege. Die bestehenden Meeting-Regressionsprüfungen wurden auf die
neuen Usecases umgestellt.

Die generierten PostgreSQL-Tabellen- und Indexdefinitionen wurden vor und nach
dem Umbau verglichen. Das Schema und die Migrationen bleiben unverändert.
Es wurden keine echten myTischtennis-Aufrufe oder Imports gegen die lokale
PostgreSQL-Datenbank als Teil dieses Umbaus ausgeführt.
