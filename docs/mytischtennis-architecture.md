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

`app/bootstrap/competition_sync.py` setzt die konkreten Implementierungen zusammen.
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

`application/sync/imports.py` enthält normale Python-Dataclasses für Spielplan,
Begegnungsdetails, Spieler, Meldungen und Tabellenstände. Halbserien und
Terminregeln liegen in der Domain; Mannschaftszuordnung und Übersetzung in
Domainobjekte stehen in `application/sync/mapping.py`.
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

API-Fehlercode 449 im JSON wird zentral im Datenquellen-Adapter behandelt:
Der identische Abruf wird nach 2, 5 und 10 Sekunden wiederholt (höchstens vier
Versuche). Das gilt auch für direkte Aufrufe durch den geplanten Worker.
Nach Ausschöpfen dieses Budgets wird ein `SourceError` ohne weitere
Batch-Wiederholung ausgelöst. Andere API-Fehler und ungültige Daten lösen diese
449-Wiederholung nicht aus. Logs enthalten nur Code, Wartezeit und Versuch,
keine fremden Fehlermeldungen oder Rohantworten. Diagnose-Probes verwenden
weiterhin den unveränderten HTTP-Client und zeigen die erste Antwort direkt.

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
ausgeschlossen. Der separate Content-Worker startet regelmäßige aktuelle
Spielimporte; siehe [Content-Automation](content-automation.md).

## Technische Import-Ereignisse und Outbox

`application/events.py` definiert den unveränderlichen Datenvertrag
`TeamMatchResultsImported`, öffentlich zugänglich über `competition/public.py`.
Er beschreibt den ersten erfolgreichen Detailimport eines Rundenspiels und enthält
eine UUID als Ereignis-ID, die interne Begegnungs-ID, den Importzeitpunkt in UTC
und die Importherkunft. Bei späteren Zustellversuchen bleibt die Ereignis-ID gleich.
Dieser Vertrag ist unabhängig von den Kalenderterminen in `content/events`.

`SyncMeetingCommand` und `SyncExternalMeetingCommand` tragen `import_origin`:
`SyncCurrent` setzt `CURRENT`, `SyncHistory` setzt `HISTORY`. Direkte Einzelimporte
verwenden standardmäßig `MANUAL`; `SyncExternalMeeting` reicht Herkunft und
`force` unverändert weiter. Die Herkunft beschreibt den gestarteten Ablauf,
nicht das Alter eines Spiels oder den Datenanbieter.

`SyncMeeting` speichert beim ersten Detailimport das Ereignis über den
`CompetitionEventOutbox`-Port. `SqlCompetitionEventOutbox` verwendet dieselbe
Session wie das Competition-Repository. Ergebnisse, Importmarkierung und Nachricht
werden gemeinsam committet oder zurückgerollt. Ein Fehler beim Schreiben der
Nachricht lässt somit auch den Detailimport scheitern; ein erneuter Versuch ist möglich.

Nach dem externen Abruf lädt der Usecase die Begegnung mit einer Schreibsperre
(`SELECT FOR UPDATE`) und prüft die Importmarkierung erneut. Das verhindert,
dass parallele Importe denselben Erstimport zweimal melden. `force=True` erlaubt
das erneute Speichern der Ergebnisse, erzeugt aber kein weiteres Erstimport-Ereignis.
Bereits vor Einführung der Outbox importierte Begegnungen werden nicht nachträglich
gemeldet. Die UUID entsteht nur beim Erstimport; die Uhr liefert denselben
Zeitpunkt für Importmarkierung und Ereignis.

Die neue Tabelle `outbox_message` liegt unter `persistence/messaging`, getrennt
von Kalenderterminen. Sie speichert UUID, versionierten Nachrichtentyp
`competition.team_match_results_imported.v1`, UTC-Zeitpunkt, JSON-Nutzdaten
(`team_match_id`, `import_origin`) und den zunächst leeren Verarbeitungszeitpunkt.
Ein eindeutiger Schlüssel aus Nachrichtentyp und Spiel-ID schützt zusätzlich vor
doppelten Erstimport-Nachrichten. Es gibt bewusst keinen Fremdschlüssel auf das
Spiel: Löschen des Spiels löscht keine ausstehende Nachricht. Ein späterer
Empfänger muss ein inzwischen fehlendes Spiel behandeln können.

Migration `e2a71d9f6b40` ergänzt ausschließlich die Outbox-Tabelle und ihren Index.
Vor Nutzung des erweiterten Detailimports muss die Datenbank auf diesen Stand
gebracht werden. Bestehende Spiel-, Termin- und Artikeltabellen bleiben unverändert.

Der Outbox-Verarbeiter reserviert Nachrichten nach dem Commit und stellt sie dem
Berichts-Handler zu. Dieser verarbeitet ausschließlich `CURRENT` bei
`report_expected=True` automatisch. Historische Erstimporte erzeugen ebenfalls
ein Ereignis, lösen aber keine automatische Berichtserstellung aus. Manuell
angeforderte Berichte werden separat über den Bericht-Usecase gestartet.
Reservierungen, Fehler und Wiederholungen sind in [Content-Automation](content-automation.md)
beschrieben. Migration `f3b82e0a7c51` ergänzt dafür die Verarbeitungsfelder.

## Start und Prüfung

Der Content-Worker verwendet eine datenbankgestützte Zeitplanung mit Nachtlauf
und gezielten Ergebnisabrufen ab drei Stunden nach Spielbeginn. Letzter Status,
Fehler und Einstellungen sind über ADMIN-Endpunkte verfügbar. Die bisherigen
direkten CLI-Importbefehle bleiben unabhängig davon. Siehe
[Zeitplanung und Admin-API](mytt-automation.md).

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

Die Outbox-Tests prüfen Erstimport, alle Importherkünfte, Wiederholung und Force,
Rollback bei Outbox-/Commit-Fehlern sowie die erneute Prüfung der Importmarkierung.
Optionale PostgreSQL-Tests in `test_outbox_postgres.py` prüfen die gesamte
Migrationskette ab leerer Datenbank, das Upgrade vom bisherigen Stand einschließlich
Datenerhalt, Schemaabgleich und parallele Importe mit echten Zeilensperren.
Sie benötigen `TTC_TEST_POSTGRES_URL` mit CREATEDB-Recht und erstellen/löschen nur
zufällig benannte eigene Testdatenbanken. Ohne diese Variable werden sie übersprungen.
Es erfolgen keine echten myTischtennis-Aufrufe und keine Migrationen der bestehenden
Entwicklungsdatenbank durch diese Tests.
