# Automatische Spielberichte: Backend-Ablauf

## Implementiert

```text
Geplanter allgemeiner Abgleich / gezielter Spielabruf
  → Spielplan aktualisieren, abgeschlossene Details importieren
  → Ergebnisse + TeamMatchResultsImported gemeinsam committen
  → Outbox-Verarbeiter reserviert die Nachricht
  → MatchResultsImportedHandler prüft CURRENT
  → CreateMatchReportDraft prüft report_expected und Ergebnisverfügbarkeit
  → Textvorlage → Artikel DRAFT
  → Nachricht als verarbeitet markieren
```

Der Handler verwendet denselben Usecase wie der manuelle CLI-Aufruf.
Historische und manuelle Detailimporte erzeugen ebenfalls Nachrichten, lösen
aber keine automatische Berichtserstellung aus. Eine manuelle Berichtsanforderung
kann auch ältere Spiele und Termine ohne Berichtserwartung verarbeiten.
Es werden weder Artikel veröffentlicht noch externe KI-Dienste aufgerufen.
Admin-HTTP-Endpunkte für Sync-Steuerung und Outbox sind implementiert; Webseiten-
Bedienung und HTTP-Endpunkte für Berichtserstellung/-bearbeitung bleiben geplant.
Siehe [MyTischtennis-Zeitplanung und Admin-API](mytt-automation.md).

## Artikel, Daten und Autorenschaft

`core/content/articles/application/commands.py` enthält `CreateMatchReportDraft`
und `EditArticleDraft`. Ports und DTOs liegen bei Articles. Der ausgehende Adapter
liest über die öffentlichen Competition- und Events-Verträge; die Textvorlage
kennt nur den Eingabe-Datensatz. Sie gibt Klartext mit Heim-/Auswärtsperspektive,
Termin (Europe/Berlin), Ergebnis, Aufstellung, Einzel/Doppel und Sätzen aus.
Fehlende Daten werden als fehlend gekennzeichnet, nicht erfunden.

`MatchReportGenerator` ist der Austauschpunkt für eine spätere KI-Implementierung.
Die Generierung läuft außerhalb der Schreibtransaktion. Für eine langsamere
Implementierung müssen Reservierungsdauer und gegebenenfalls Lease-Verlängerung
neu betrachtet werden. Die aktuelle Vorlage benötigt keine Netzwerkzugriffe.

Migration `f3b82e0a7c51` legt einen Benutzer mit Name `System`, eindeutiger
`system_key=article-automation`, ohne Rollen und ohne gültigen Passwort-Hash an.
Er ist inaktiv. Login, Refresh und Zugriffstoken-Verwendung lehnen Systemidentitäten
auch dann ab, wenn `is_active` versehentlich aktiviert wurde. Bestehende Benutzer
werden nicht dafür umgewidmet. Es wird kein Standardpasswort angelegt.

Automatische Berichte erhalten den Systemautor. Manuelle Aufrufe können einen
aktiven ADMIN/EDITOR als Autor angeben; ohne Angabe verwenden vertrauenswürdige
CLI-Aufrufe ebenfalls den Systemautor. Bei `EditArticleDraft` wird der speichernde
ADMIN/EDITOR zum Autor. Nur DRAFT ist bearbeitbar; Titel, Teaser und Inhalt werden
validiert. Generierungsherkunft, Datum, Zuordnung, Slug und Titelbild bleiben erhalten.

Die Artikelspalten `generation_key`, `generation_method` und `generated_at`
halten die Herkunft fest. `team-match:<ID>` ist ein eindeutiger Generierungsschlüssel,
kein zusätzlicher Fremdschlüssel. Er bleibt auch beim Löschen eines Kalendertermins
erhalten; dessen bestehender Artikel-Fremdschlüssel verwendet weiterhin SET NULL.
Die Migration fügt keine weiteren Löschkaskaden hinzu.

PostgreSQL serialisiert Generierungsanfragen für dieselbe Spiel-ID mit einer
transaktionsgebundenen Advisory-Sperre. Zusätzlich schützt der eindeutige Schlüssel
gegen doppelte generierte Artikel. Bereits vorhandene Spielberichte zum selben
Kalendertermin werden ebenfalls zurückgegeben. Wiederholungen überschreiben nie
redaktionelle Texte. Bewusstes Neugenerieren ist nicht Teil dieses Workflows.

## Zustellung, Fehler und Wiederholungen

`ProcessOutbox` nutzt einen Store-Port und einen Handler-Port. Der SQL-Store
reserviert eine fällige Nachricht mit `FOR UPDATE SKIP LOCKED`, erhöht `attempts`
und speichert `lock_token` und `locked_until`. Die Reservierung wird sofort
committet; während der Berichtserstellung bleibt keine Outbox-Zeilensperre offen.

Erfolg setzt `processed_at`. Ein Fehler speichert dessen Klasse in `last_error`
und plant den nächsten Versuch mit exponentiell wachsender Wartezeit bis maximal
einer Stunde. Nach standardmäßig fünf Versuchen wird `failed_at` gesetzt.
Ungültige Nachrichten und unbekannte Nachrichtenversionen werden sofort als
fehlgeschlagen markiert. Sie blockieren keine anderen Nachrichten.
Ausnahmen werden nicht mit beliebigen SQL-Parametern in die Outbox geschrieben.

Nach einem Prozessabbruch läuft die Reservierung ab. Ein anderer Worker kann die
Nachricht übernehmen. Nur der aktuelle Reservierungstoken darf sie bestätigen;
ein verspäteter alter Worker kann keine neuere Reservierung überschreiben.
Auch nach einem Absturz im letzten Versuch wird die Nachricht als fehlgeschlagen
sichtbar. Ein Operator kann sie gezielt erneut freigeben.

Artikel-Commit und Nachrichtenbestätigung sind getrennte Transaktionen.
Stürzt der Prozess dazwischen ab, wird erneut zugestellt. Der Usecase findet
dann den bereits vorhandenen Artikel. Das ergibt wiederholbare Verarbeitung
ohne doppelte Artikel, keine Garantie einer einmaligen Handler-Ausführung.

Nachrichten bleiben einschließlich verarbeiteter Einträge gespeichert. Eine
automatische Aufbewahrungs-/Löschstrategie ist nicht Bestandteil dieses Schritts.

## Ausführen

Alle Befehle laufen aus `backend/` mit aktivierter Backend-Umgebung.
Vor Nutzung ist `alembic upgrade head` erforderlich. Die neuen Migrationen
ergänzen Tabellen/Spalten und den Systemautor; vorhandene Fachdaten bleiben erhalten.

Regelmäßigen Worker starten (führt echte myTischtennis-Imports aus):

```powershell
python -m scripts.content worker
```

Der Worker startet Sync und Outbox-Verarbeitung in getrennten Schleifen.
Standard: allgemeiner Abgleich nachts um 03:00 Europe/Berlin, gezielte Ergebnisabrufe
ab drei Stunden nach Spielbeginn. Einstellungen und Status liegen in der Datenbank;
Details einschließlich Nachholen und Wiederholungen stehen in [MyTT-Automation](mytt-automation.md).
Die Outbox läuft mit zehn Sekunden Pause zwischen Durchläufen.
Ein Sync-Fehler stoppt die Outbox-Verarbeitung nicht. Eine PostgreSQL-Prozesssperre
verhindert gleichzeitig laufende geplante Syncs. Mehrere Outbox-Worker sind möglich.
Strg+C beendet den Prozess; nach Neustart werden offene Nachrichten wieder aufgenommen.
Für Betrieb über Rechnerneustarts hinaus muss dieser Befehl durch den eingesetzten
Prozessmanager gestartet werden. Der Webserver startet den Worker nicht automatisch.

Eine fällige Sync-Aufgabe und Outbox-Verarbeitung (gegebenenfalls echter Sync):

```powershell
python -m scripts.content worker --once
```

Weitere Befehle, jeweils ohne externen Ergebnisabruf:

```powershell
python -m scripts.content generate-report 123
python -m scripts.content generate-report 123 --author-id 7
python -m scripts.content process-outbox --limit 100
python -m scripts.content outbox-status --limit 20
python -m scripts.content retry-message <ereignis-uuid>
python -m scripts.content edit-draft 42 --author-id 7 --title "Spielbericht" --teaser "Kurzfassung" --content-file bericht.txt
```

`outbox-status` liest nur. Die anderen Befehle schreiben; `retry-message` gibt eine
unverarbeitete, nicht aktuell reservierte Nachricht frei. `generate-report` gibt
Artikel-ID und `created`/`already_exists` zurück. Manuelle Erstellung und
Ereigniswiederholung sind verschiedene Dinge: Historische Nachrichten bleiben
auch nach Freigabe von der Automatik ausgeschlossen.

### Konfiguration

| Umgebungsvariable | Standard |
| --- | --- |
| `OUTBOX_POLL_INTERVAL_SECONDS` | 10 |
| `OUTBOX_BATCH_SIZE` | 100 |
| `OUTBOX_MAX_ATTEMPTS` | 5 |
| `OUTBOX_LEASE_SECONDS` | 300 |
| `OUTBOX_RETRY_SECONDS` | 60 |

## Tests

`test_report_automation.py` prüft den Import-bis-Entwurf-Ablauf mit SQLite und
gemockter Datenquelle, Herkunftsfilter, Autorenwechsel, Login-Sperre,
Fehler/Wiederholung, Reservierungsablauf und Worker-Fehlerisolation.
`test_outbox_postgres.py` prüft Migrationen, Datenerhalt und echte parallele
Imports, Generierungen und Reservierungen in wegwerfbaren PostgreSQL-Datenbanken.
Details zur opt-in Testvariable stehen in [Development](development.md).
