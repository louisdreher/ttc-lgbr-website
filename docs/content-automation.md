# Automatische Spielberichte: Backend-Ablauf

## Implementiert

```text
SyncCurrent(meetings)
  → Spielplan aktualisieren, abgeschlossene Details importieren
  → Ergebnisse + TeamMatchResultsImported gemeinsam committen
  → Outbox-Verarbeiter reserviert die Nachricht
  → MatchResultsImportedHandler prüft CURRENT
  → CreateMatchReportDraft prüft report_expected und Ergebnisverfügbarkeit
  → Textvorlage → Artikel DRAFT
  → Nachricht als verarbeitet markieren
```

Der Handler verwendet denselben Usecase wie ein manueller Python-Aufruf.
Historische und manuelle Detailimporte erzeugen ebenfalls Nachrichten, lösen
aber keine automatische Berichtserstellung aus. Eine manuelle Berichtsanforderung
kann auch ältere Spiele und Termine ohne Berichtserwartung verarbeiten.
Es werden weder Artikel veröffentlicht noch externe KI-Dienste aufgerufen.
HTTP-Endpunkte und Webseiten-Bedienung für diese Funktionen sind nicht implementiert.

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


Worker und CLI-Anbindung werden im nächsten Schritt ergänzt.
