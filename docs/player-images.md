# Spielerbildhistorie

## Vereinbarte Regeln

Ein Spielerbild gilt ab der Saison und Halbserie der bearbeiteten Mannschaft
bis zur nächsten Bildzuordnung. Der Uploadzeitpunkt bestimmt die Gültigkeit nicht.
Wird heute die Vorrunde 2009/10 bearbeitet, gilt das neue Bild ab dieser Vorrunde.
Eine bestehende Zuordnung derselben Halbserie wird ersetzt. Frühere Halbserien
und spätere ausdrücklich gesetzte Bilder bleiben erhalten.

Zur Anzeige wird die letzte Zuordnung bis zur gewünschten Halbserie verwendet:
zuerst nach Saisonstartjahr, dann Vorrunde vor Rückrunde sortieren (nicht
alphabetisch nach `vr`/`rr`). Ohne neues Bild gilt das alte weiter; vor dem ersten
Bild erscheint ein Platzhalter. Alle Mannschaften eines Spielers teilen die Historie.

## Implementiert: Persistenzmodell und Migrationen

`PlayerImage` liegt im Members-Persistenzadapter. Migration `f6b48c73d957`
erstellt die Tabelle; die Folgemigration `a8c59d84e068` ergänzt `season_half`.
Der Primärschlüssel besteht aus `player_id`, `season_start_year` und
`season_half`. Die verpflichtende Halbserie erlaubt nur `vr` und `rr`.
`media_id` referenziert das Bild. Competition-Saison-IDs und ein Enddatum
werden nicht benötigt.

Vor Verwendung der Mannschaftsansicht muss die Datenbank bis einschließlich
`a8c59d84e068` migriert sein (`python -m alembic upgrade head` im Backend-Verzeichnis).
Fehlt `player_image`, funktioniert eine leere Aufstellung noch, die erste
Zuordnung führt beim anschließenden Lesen der Bildhistorie jedoch zu einem Fehler.
Ein fehlendes Bild ist dagegen regulär und wird als Platzhalter angezeigt.

Bestehende ganzjährige Einträge werden der Vorrunde zugeordnet. Der Downgrade
zur Ganzjahrestabelle wird bei vorhandenen Rückrundenbildern abgebrochen, damit
kein Bildwechsel verloren geht. Diese Einträge müssen vorher ausdrücklich
aufgelöst werden. Die ursprüngliche Migration bleibt unverändert.

Fremdschlüssel sichern Spieler und Medienreferenz. Es gibt kein kaskadierendes
Löschen: Referenzierte Spieler und Medien können nicht ohne vorherige explizite
Auflösung ihrer Bildzuordnungen gelöscht werden. Das Ersetzen einer Referenz
löscht keine Mediendatei. Der Downgrade der ursprünglichen Migration entfernt die
Bildhistorientabelle samt deren Einträgen.

## Implementiert: Bildauswahl

`core/members/public.py` exportiert `GetPlayerImages` und `GetPlayerImagesQuery`.
Die Query nimmt `player_ids` als `frozenset[int]`, `season_start_year` und
`season_half` (`vr` oder `rr`) entgegen. Das Ergebnis ist `dict[int, int | None]`:
Jede angefragte Spieler-ID bekommt eine Medien-ID oder `None`. Auch unbekannte
Spieler-IDs ergeben `None`; diese Bildabfrage ersetzt keine Existenzprüfung
beim Schreiben.

Der Usecase verwendet den Members-eigenen Port `PlayerImageReader`.
`SqlPlayerImageReader` filtert zukünftige Zuordnungen aus und wählt mit
`row_number()` pro Spieler den jüngsten gültigen Eintrag. Die Halbserien
werden explizit chronologisch verglichen. Alle Spieler werden mit einem SELECT
abgefragt; das Ergebnis enthält maximal eine Bildreferenz je Spieler.
Leere Anfragen öffnen keine Datenbanksitzung.

`bootstrap/members.py:build_get_player_images()` verdrahtet die Abfrage.
Tests prüfen Halbseriengrenzen, jahrelange Weiterverwendung, fehlende und
zukünftige Bilder sowie die gebündelte Abfrage ohne Schreibzugriffe.

## Implementiert: Mannschaftsansicht im CMS

Die ADMIN-geschützte Aufstellungsabfrage ergänzt `media_id` über den öffentlichen
Members-Vertrag. Maßgeblich ist die Saison der angefragten Mannschaft.
Das CMS bietet unter `/admin/teams` eine Saison-/Halbserienwahl und eine Zeilenliste
der Mannschaften mit Kategorie und Bearbeiten-Link. `/admin/teams/:teamId` zeigt
die separate Detailseite mit interner Aufstellung, Position, Status und Bild.
Der URL-Parameter `season` bewahrt die Auswahl beim Öffnen und Zurückkehren;
direkte Detailaufrufe verwenden für den Rückweg die Saison der geladenen Mannschaft.
Fehlende Bilder erhalten einen
Platzhalter; Bildvorschauen verwenden den bestehenden geschützten Medienendpunkt.
Die wiederverwendbare Frontend-Komponente `PlayerPortrait` zeigt bei fehlender
Medien-ID das statische Bild `/images/player-placeholder.png` mit dem Alternativtext
„Kein Spielerfoto vorhanden“. Das Ersatzbild wird weder als Medium noch als
Bildhistorieneintrag gespeichert. Vorhandene Medien-IDs nutzen weiter `MediaPreview`;
Ladefehler werden dort als Fehler angezeigt und nicht mit fehlenden Bildern verwechselt.

## Implementiert: Upload und Bildwechsel

Der Bild-Button einer Spielerzeile öffnet den bestehenden Upload-Dialog für eine
Datei. Nach dem Upload ordnet `PUT /api/competition/teams/{team_id}/lineup/{player_id}/image`
das Medium zu (Body: `media_id`). Beide Schritte erfordern ADMIN. Der Server
bestimmt Saison und Halbserie aus der Mannschaft und prüft die interne Zuordnung.
Clientseitige Zeitangaben werden nicht akzeptiert.

`AssignPlayerImage` gehört zu Members und verwendet einen eigenen Repository-/
Unit-of-Work-Port. Explizite SQL-Verträge von Competition und Media prüfen
Aufstellung und Bildreferenz in derselben Transaktion. Die Mannschaftssperre
verhindert gleichzeitiges Entfernen; die Spielersperre serialisiert Bildwechsel
auch über mehrere Mannschaften. Die Medienreferenz wird mit einer Lesesperre
geschützt. Repositories committen nicht selbst.

Ein vorhandener Eintrag derselben Halbserie wird ersetzt; ältere und spätere
Einträge bleiben bestehen. Das Bild gilt für den Spieler in allen Mannschaften
ab dieser Halbserie bis zum nächsten Historieneintrag. MyTT schreibt diese
Historie nicht. Eine neue Migration ist für diese Bedienung nicht erforderlich.

Schlägt die Zuordnung nach erfolgreichem Upload fehl, bleibt die Medien-ID im
CMS zum erneuten Speichern erhalten. Das bereits hochgeladene Medium bleibt
gespeichert; der Upload muss nicht wiederholt werden.
