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

Ein Worker führt pro Tick eine Aufgabe aus. Ein langer allgemeiner Lauf kann
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

Tests prüfen Nachtlauf, Sommer-/Winterzeit, Spieltermine, Wiederholungen,
Konfigurationsänderungen, unterbrochene Läufe, Admin-Berechtigungen und den
Abruf-bis-Bericht-Ablauf. PostgreSQL-Tests prüfen neue und bestehende Datenbanken,
Schemaabgleich, gleichzeitige Änderungen und Prozesssperren ohne echte externe
Abrufe. Der Admin-Tab selbst bleibt Frontend-Arbeit.
