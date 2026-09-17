# myTischtennis: Zeitplanung und Admin-API

## Betrieb

Nach `alembic upgrade head` startet `python -m scripts.content worker` den
separaten Prozess. FastAPI startet keinen Worker. Migration `a7c93d1e8402`
ergänzt Einstellungen/Status und den letzten Abrufversuch je Spiel. Vorhandene
Spiele, Ergebnisse und Artikel werden nicht geändert. Der Fremdschlüssel der
Abrufmarkierung verwendet ON DELETE CASCADE: Beim Löschen eines Spiels entfällt
nur dessen technische Abrufmarkierung.

Die Zeitplanung liegt in der Datenbank. Änderungen gelten bei der nächsten
Aufgabenauswahl, laufende Aufgaben verwenden ihre beim Start gelesenen Einstellungen.
Der Worker prüft alle 15 Sekunden lokal auf fällige Aufgaben. Das ist kein
myTischtennis-Abruf. Die Outbox läuft weiterhin unabhängig davon.

### Nachtlauf

Standard ist 03:00 Uhr Europe/Berlin. Der allgemeine Abgleich lädt den aktuellen
Spielplan einmal und danach Tabellen und Aufstellungen der aktuellen Halbserie.
Die beiden letzten Schritte sind einzeln abschaltbar. Jede Aufgabe wird als
letzter allgemeiner Lauf gespeichert; es gibt keine Historientabelle.

Beim ersten Start und nach Ausfall wird der zuletzt fällige Nachtlauf einmal
nachgeholt, nicht jeder verpasste Tag. Ein fehlgeschlagener Nachtlauf wird nicht
alle 15 Sekunden wiederholt: Er bleibt sichtbar und kann manuell angefordert
werden; ansonsten folgt der nächste Nachttermin. Ein beim Prozessabbruch offen
gebliebener allgemeiner Lauf wird bei Übernahme der Prozesssperre neu angefordert.
Bei Sommerzeit wird eine nicht vorhandene Uhrzeit nach vorne verschoben
(02:30 → 03:30); die doppelte Herbststunde wird nur beim ersten Auftreten ausgeführt.

### Gezielte Ergebnisabrufe

Aus den gespeicherten Ansetzungen ergibt sich der erste Abruf: Beginn + drei
Stunden. Dabei wird direkt das einzelne Spiel abgefragt, ohne den gesamten
Spielplan erneut zu laden. Noch unvollständige Ergebnisse werden standardmäßig
alle 30 Minuten geprüft, bis 24 Stunden nach dem ersten vorgesehenen Abruf.
Auch technische Fehler unterliegen diesem Abstand und Fenster. Ein letzter
erfolgloser Versuch am Ende des Fensters wird als Fehler angezeigt.

Nur Spiele mit externer ID ohne abgeschlossenen Detailimport werden eingeplant.
Geänderte Ansetzungen machen eine alte Abrufmarkierung ungültig. Nach Neustarts
werden überfällige Abrufe innerhalb des Fensters nachgeholt. Liegt das gesamte
Fenster bereits in der Vergangenheit, wird das Spiel nicht automatisch geladen;
historische Importe bleiben explizite Aktionen. Insbesondere löst ein Start mit
vielen alten Spielen keine historischen automatischen Berichte aus.

Der Nachtlauf lädt selbst keine historischen Details nach. Nach seiner
Spielplanaktualisierung werden fällige aktuelle Spiele in den folgenden Ticks
abgearbeitet. Neue Ergebnisse verwenden `ImportOrigin.CURRENT`; die vorhandene
Outbox erzeugt nur bei `report_expected=True` einen Berichtsentwurf.

Ein Worker führt pro Tick eine Aufgabe aus. Manuelle Einzelspielaufträge werden
vor allgemeinen Anforderungen, Nachtläufen und automatischen Spielabrufen gewählt.
Ein langer bereits gestarteter allgemeiner Lauf kann
gezielte Abrufe verzögern. Die bestehende PostgreSQL-Advisory-Sperre verhindert
parallel laufende geplante Aufgaben über mehrere Worker hinweg. Sie gilt für den
Worker einschließlich Admin-Anforderungen, nicht für ältere direkt aufgerufene
Import-/Diagnoseskripte. Bereits gestartete Abrufe werden durch Änderungen oder
Pausieren nicht abgebrochen. Kurzfristige Spielplanänderungen erfährt der Worker
beim nächsten allgemeinen Abgleich; bei Bedarf diesen manuell anfordern.

## Admin-Endpunkte

Alle Endpunkte verlangen einen angemeldeten ADMIN. EDITOR allein genügt nicht.
FastAPI validiert Eingaben und ruft Usecases auf; GET startet niemals einen Sync.

| Methode | Pfad | Bedeutung |
| --- | --- | --- |
| GET | `/api/admin/mytt/status` | Einstellungen, aktueller/letzter Lauf, letzter allgemeiner Lauf, Fehler, Lebenszeichen, nächste Fälligkeiten |
| GET | `/api/admin/mytt/settings` | Einstellungen lesen |
| PUT | `/api/admin/mytt/settings` | Einstellungen vollständig ersetzen; ausgelassene Felder erhalten Standardwerte |
| POST | `/api/admin/mytt/sync` | Allgemeinen Abgleich anfordern; 202, sobald die Anforderung gespeichert ist |
| GET | `/api/admin/mytt/outbox?limit=20` | Neueste Nachrichten ohne Nutzdaten und Reservierungstoken; Limit 1–1000 |
| POST | `/api/admin/mytt/outbox/{event_id}/retry` | Nachricht erneut freigeben; 204, bei nicht erlaubter Wiederholung 409 |
| GET | `/api/admin/mytt/matches` | Letzte zehn importierte Spiele, alle abgeschlossenen ohne Details, nächste drei anstehende Spiele |
| POST | `/api/admin/mytt/matches/{match_id}/reload` | Detailimport eines abgeschlossenen Spiels dauerhaft anfordern; 202 mit Auftragsstatus |

Eine manuelle Anforderung wird in der Datenbank gespeichert. Mehrere wartende
Anforderungen werden zu einer zusammengefasst. Während eines Laufs kann eine
weitere Anforderung vorgemerkt werden. Auch bei deaktivierter Automatik bleibt
ein explizit angeforderter allgemeiner Abgleich möglich. Ohne Worker bleibt die
Anforderung offen; 202 bedeutet nicht, dass der Import bereits abgeschlossen ist.

Beispiel für PUT `/api/admin/mytt/settings`:

```json
{
  "enabled": true,
  "nightly_hour": 3,
  "nightly_minute": 0,
  "result_delay_minutes": 180,
  "result_retry_minutes": 30,
  "result_retry_window_hours": 24,
  "include_tables": true,
  "include_registrations": true
}
```

Grenzen: Verzögerung 0–1440 Minuten, Wiederholung 5–1440 Minuten,
Nachlaufzeit 1–168 Stunden. Die Zeitzone bleibt Europe/Berlin. Die alte
Umgebungsvariable `COMPETITION_SYNC_INTERVAL_SECONDS` wird nur noch für vorhandene
`.env`-Dateien akzeptiert und steuert die Zeitplanung nicht mehr.

## Status ohne Historie

### Spieleübersicht und manuelles Nachladen

`GET /api/admin/mytt/matches` ist rein lesend. `GetSyncMatches` verwendet einen
eigenen `SyncMatchOverviewReader`-Port mit frameworkfreien DTOs. Die drei Gruppen
werden in SQL ausgewählt, ohne Saison- oder automatischen Zeitfensterfilter:

| JSON-Feld | Auswahl | Reihenfolge |
| --- | --- | --- |
| `imported` | `details_imported_at IS NOT NULL`, höchstens zehn | Detailimportzeit absteigend, Spiel-ID aufsteigend |
| `missing_details` | `is_completed = true` und `details_imported_at IS NULL`, alle | Spielbeginn aufsteigend (älteste zuerst), Spiel-ID aufsteigend |
| `upcoming` | Spielbeginn strikt nach Abfragezeitpunkt, nicht abgeschlossen und ohne Detailimport, höchstens drei | Spielbeginn aufsteigend, Spiel-ID aufsteigend |

Die Zusatzbedingungen bei `upcoming` halten die Gruppen auch bei widersprüchlichen
Daten getrennt: Ein bereits abgeschlossenes Spiel mit künftigem Termin gehört
zu `missing_details` oder `imported`. Leere Gruppen sind leere Arrays. Bei einem
Gleichstand gibt die interne ID eine stabile Reihenfolge vor. Alle Zeitstempel
werden als UTC-Zeitstempel ausgegeben.

Ein Spieleintrag hat folgendes Schema (hier vor einer Anforderung):

```json
{
  "id": 123,
  "team_id": 7,
  "team_name": "TTC I",
  "opponent_name": "Gastverein",
  "is_home": true,
  "scheduled_at": "2026-09-01T18:00:00Z",
  "is_completed": true,
  "details_imported_at": null,
  "reload": null,
  "can_reload": true,
  "reload_blocked_reason": null
}
```

`reload` ist null, solange noch kein manueller Auftrag existiert. Andernfalls
enthält es den unten beschriebenen Status. Fehlende externe IDs, nicht abgeschlossene
oder bereits importierte Spiele, offene Aufträge und laufende automatische Abrufe
ergeben `can_reload=false` mit einem verständlichen Grund. Das ist eine Momentaufnahme;
POST prüft erneut. Wiederholte POSTs für einen offenen Auftrag sind trotz
`can_reload=false` idempotent und liefern dessen bestehenden Status.

`POST /api/admin/mytt/matches/123/reload` benötigt keinen Request-Body und antwortet
erst nach dem Speichern mit 202, beispielsweise:

```json
{
  "team_match_id": 123,
  "status": "requested",
  "requested_at": "2026-09-18T21:00:00Z",
  "started_at": null,
  "finished_at": null,
  "last_error": null
}
```

HTTP-Regeln: 401 ohne Anmeldung, 403 ohne ADMIN, 404 für ein unbekanntes Spiel,
422 für eine ungültige ID, 409 für bereits importierte, noch nicht abgeschlossene
oder ohne externe ID gespeicherte Spiele sowie einen bereits laufenden automatischen
Abruf. Es wird weder ein Import direkt ausgeführt noch implizit `force` verwendet.

### Speicherung und Auftragslebenszyklus

Migration `b8d04e2f9513` ergänzt ausschließlich `mytt_match_reload` mit genau einer
Zeile je Spiel (Spiel-ID als Primär-/Fremdschlüssel), vier Statuswerten, Zeitstempeln
und dem letzten bereinigten Fehler. Ein Index unterstützt die Queue-Auswahl.
ON DELETE CASCADE entfernt beim Löschen eines Spiels nur dessen technischen Auftrag.
Die Migration verändert keine bestehenden Spiel-, Ergebnis- oder Outboxdaten.
Vor Nutzung muss sie mit `alembic upgrade head` angewendet werden.

Der Lebenszyklus ist `requested → running → succeeded/failed`. Doppelte offene
Anforderungen ändern weder Anforderungszeit noch Auftrag. Nach `failed` setzt eine
erneute Anforderung dieselbe Zeile auf `requested` und leert die vorherigen
Bearbeitungszeiten und Fehler. Es entsteht keine unbegrenzte Auftragshistorie.

Worker-Priorität: ältester manueller Einzelspielauftrag (Anforderungszeit, dann
Spiel-ID), allgemeine manuelle Anforderung, fälliger Nachtlauf, automatischer
Einzelspielabruf. Manuelles Nachladen gilt unabhängig von `enabled` und Abruffenster.
Eine bereits laufende Aufgabe wird nicht unterbrochen. Ein Spiel mit einem manuellen
Auftrag bleibt von automatischen Abrufen ausgeschlossen, auch nach einem Fehler.
So übernimmt die Automatik einen fehlgeschlagenen manuellen Import nicht später
mit anderer Herkunft; der ADMIN kann ihn ausdrücklich erneut anfordern.

Enqueueing und Aufgabenauswahl werden in kurzen Transaktionen über die vorhandene
Singleton-Zeilensperre serialisiert. Die bestehende PostgreSQL-Advisory-Sperre
schützt die gesamte Worker-Ausführung. Während externer Abrufe bleiben keine
Status-/Auftrags-Zeilensperren offen; Heartbeat und Outbox laufen unabhängig.
Ein POST während eines automatischen Abrufs desselben Spiels erhält 409 statt
den laufenden Abruf zu übernehmen. Nach einem Absturz kann dieser Konflikt bis zur
nächsten Worker-Sperrübernahme bestehen bleiben.

Nach Übernahme der Prozesssperre erkennt der Worker zurückgebliebene `running`-
Aufträge als unterbrochen und übernimmt sie erneut. Er prüft unmittelbar vor dem
Import nochmals Abschlussstatus, externe ID und Detailimportmarkierung. Sind
Ergebnisse bereits gespeichert (auch bei Absturz zwischen Ergebnis-Commit und
Auftragsbestätigung), wird nur der Auftrag bestätigt. Der Import-Usecase prüft
die Importmarkierung zusätzlich unter seiner vorhandenen Spiel-Zeilensperre.

`SyncMeeting` wird mit `ImportOrigin.MANUAL` und ohne `force` verwendet. Sein
Erstimport-Ereignis und die transaktionale Outbox bleiben unverändert. Die
Outbox verarbeitet das Ereignis, erzeugt wegen `MANUAL` aber keinen automatischen
Berichtsentwurf, auch nicht bei `report_expected=True`.

Fehlende vollständige Provider-Ergebnisse gelten als fehlgeschlagener Auftrag.
Technische Fehler speichern nur die Exception-Klasse; eigene fachliche Fehler
verwenden kontrollierte Texte. Zugangsdaten und rohe Provider-Antworten werden
nicht übernommen. Die bestehende begrenzte Wiederholung bei API-Code 449 bleibt
im Quellenadapter erhalten. Darüber hinaus werden fehlgeschlagene manuelle
Aufträge erst nach einer neuen ADMIN-Anforderung wieder ausgeführt.

Das globale `state.last_run` zeigt auch manuelles Nachladen als `kind="match"`
mit Spiel-ID an; der letzte allgemeine Abgleich wird dadurch nicht überschrieben.
Den spezifischen Nachlade-Status liefert `reload` in der Spieleübersicht.
Die Angular-Anbindung für Spieleübersicht und Nachladen ist separat implementiert;
ihre Bedienung ist im Abschnitt „Angular-Administration“ beschrieben.

### Allgemeiner Worker-Status

`state.last_run` enthält den aktuellen beziehungsweise zuletzt abgeschlossenen
Auftrag mit Art (`nightly`, `manual`, `match`), optionaler Spiel-ID, Start/Ende,
Zählern und Fehlerklassen. Statuswerte: `running`, `succeeded`, `partial`, `failed`,
`waiting` (noch keine vollständigen Ergebnisse). Die Zähler stehen nach Abschluss
bereit; sie sind keine laufende Fortschrittsanzeige. `state.nightly_run` bewahrt
unabhängig von Einzelspielen den letzten allgemeinen Abgleich (auch manuell).
`last_nightly_success_at` zeigt den letzten vollständig erfolgreichen allgemeinen
Abgleich. Die Zähler des allgemeinen Laufs zählen erfolgreich bearbeitete
Teilschritte, nicht Spiele.

`state.last_error` und `last_error_at` bleiben über nachfolgende Erfolge hinweg
als zuletzt beobachteter Fehler erhalten. Externe Fehlermeldungen werden nicht
unverändert gespeichert, damit keine Zugangsdaten oder Rohantworten ausgegeben
werden. Neben Fehlerklassen erscheinen gegebenenfalls Aufgabe und Gruppen-ID.

Der Worker schreibt unabhängig vom Sync alle 15 Sekunden ein Lebenszeichen.
Nach 90 Sekunden ohne Lebenszeichen gilt er als offline. Ein offener Lauf wird
dann als `stale_run` statt als sicher laufend angezeigt. Das Lebenszeichen sagt,
dass mindestens ein Worker aktiv ist; es ist keine Garantie für erreichbare
myTischtennis-Dienste. Die nächste Sperrübernahme erkennt und behandelt einen
abgebrochenen Lauf. UTC-Zeitstempel eignen sich zur lokalen Anzeige im Frontend.

`next_nightly_at` und `next_match_at` sind Fälligkeiten nach den aktuellen Regeln,
keine garantierten Startzeiten. Bei überfälligen Aufgaben steht dort der aktuelle
Zeitpunkt. Bei deaktivierter Automatik sind beide null; `state.requested` zeigt
eine separate manuelle Anforderung.

CLI für Betrieb ohne Frontend:

```powershell
python -m scripts.content sync-status
python -m scripts.content request-sync
python -m scripts.content worker --once
```

`worker --once` führt höchstens eine fällige Aufgabe plus Outbox-Verarbeitung aus.
Für einen ausdrücklich gewünschten allgemeinen Abgleich vorher `request-sync`
verwenden. Die normalen Report-/Outbox-Befehle bleiben verfügbar.

## Code und Prüfung

Regeln: `core/competition/domain/sync_automation.py`. Usecases und Ports:
`core/competition/application/sync/automation/`. SQL-Adapter:
`persistence/competition/automation.py`. Verdrahtung:
`bootstrap/competition_automation.py`. HTTP: `competition/automation_*`.

## Angular-Administration

Unter `/admin/mytt` ist der Tab **MyTischtennis** für ADMIN verfügbar. Die
Navigation blendet ihn für andere Rollen aus; ein eigener Route-Guard schützt
auch den direkten Aufruf. Der vorhandene Auth-Interceptor übernimmt die Anmeldung.

Status, Spieleübersicht und die letzten 20 Outbox-Nachrichten werden beim Öffnen und alle 15 Sekunden
geladen. Beim Verlassen werden Timer und offene HTTP-Aufrufe beendet. Fehler beim
Aktualisieren kennzeichnen vorhandene Daten als möglicherweise veraltet. Das
Einstellungsformular wird separat geladen, damit Polling keine Eingaben überschreibt.
Gespeichert wird immer der vollständige Einstellungsdatensatz.

Der Button **Spielplan synchronisieren** zeigt eine bestätigte Anforderung als
**Angefordert** und einen aktiven allgemeinen Lauf als **Synchronisierung läuft**.
Er lädt weiterhin auch Tabellen und Aufstellungen gemäß den gespeicherten Einstellungen.
Worker-Erreichbarkeit wird farblich und als Text angezeigt, zusammen mit den nächsten
Fälligkeiten und dem Zeitpunkt der letzten erfolgreichen Statusabfrage. Eine aktive
Aufgabe wird nur bei offenem Lauf angezeigt; der letzte Spielplan-Abgleich bleibt sichtbar.
Zeitstempel erscheinen in der lokalen Browser-Zeitzone;
die eingegebene Nachtlaufzeit gilt weiterhin für Europe/Berlin. Die Outbox erlaubt
erneute Freigaben unverarbeiteter, nicht aktiv reservierter Nachrichten und erklärt
409-Konflikte, falls sich deren Zustand inzwischen geändert hat.

Die drei Spielgruppen **Details fehlen**, **Anstehend** und **Erfolgreich geladen**
sind einzeln einklappbar; die erfolgreichen Importe sind zunächst geschlossen.
Die Reihenfolge und Auswahl übernimmt das Frontend aus `/matches`. Je fehlendem
Detailimport fordert **Details nachladen** einen Worker-Auftrag an. `can_reload`
und `reload_blocked_reason` steuern die Verfügbarkeit der Aktion. Die Zeile zeigt
Anforderung, laufende Verarbeitung oder Fehler; bei unbekannter Worker-Erreichbarkeit
wird ein laufender Auftrag als unklar gekennzeichnet. Ein bestätigter POST allein
gilt nicht als erfolgreicher Import. Nach erfolgreichem Detailimport erscheint das
Spiel beim nächsten Polling in der Gruppe der letzten zehn Importe.
Nachladen erzeugt keine automatischen Berichtsentwürfe. 404-/409-Konflikte und
Verbindungsfehler werden verständlich angezeigt und die Übersicht erneut gelesen.

Tests prüfen Nachtlauf, Sommer-/Winterzeit, Spieltermine, Wiederholungen,
Konfigurationsänderungen, unterbrochene Läufe, Admin-Berechtigungen und den
Abruf-bis-Bericht-Ablauf. PostgreSQL-Tests prüfen neue und bestehende Datenbanken,
Schemaabgleich, gleichzeitige Änderungen und Prozesssperren ohne echte externe
Abrufe. Frontend-Tests prüfen außerdem ADMIN-Zugriff, Navigation, Polling und dessen
Abbruch, 202-Anforderungen, Formulareingaben, Fehlerzustände und Outbox-Freigaben.
