# Articles: CMS und Veröffentlichung

## Fachlicher Ablauf

`TEAM_REPORTER`, `EDITOR` und `ADMIN` dürfen Beiträge schreiben. Nur EDITOR und
ADMIN dürfen die Redaktion nutzen, fremde Beiträge bearbeiten und veröffentlichen.
Weitere Schreibrollen können später in der HTTP-Abbildung auf `ArticleActor`
ergänzt werden. Der Actor kommt ausschließlich aus der authentifizierten Session,
nicht aus dem Request-Body; er enthält Fähigkeiten statt frameworkabhängiger Rollen.
Die Use Cases prüfen zusätzlich Eigentümerschaft, Sichtbarkeit und erlaubte Aktionen.

Jeder Artikel hat einen Autor. Automatische Entwürfe gehören zum Systembenutzer
`article-automation`. Ein Systementwurf wird beim ersten Speichern oder Einreichen
dem schreibenden Benutzer zugeordnet. Redaktionelle Korrekturen an einem bereits
zugeordneten Beitrag ändern dessen Autor nicht. Generierungsherkunft bleibt erhalten.

Die Vorbereitung für einen Event speichert nichts. Sie liefert entweder die Inhalte
des vorhandenen Systementwurfs oder Titel und Beschreibung des Events als Startwerte.
Ohne Artikel entstehen ein Slug `bericht-{event_id}`, ein leerer Teaser und leere
Tags; eine fachliche Zuordnung von Event-Kategorien zu Artikel-Tags besteht noch nicht.
Ein Systementwurf liefert dagegen auch seine vorhandenen Tags und sein Titelbild.
Es wird bei dieser Leseabfrage keine Textgenerierung gestartet.

Unter „Neuer Beitrag“ erscheinen vergangene Events ohne Artikel oder mit einem Systementwurf
im Status DRAFT. Als Zeitgrenze zählt das Ende, ersatzweise der Beginn; der Zeitpunkt
muss vor der serverseitigen Abfragezeit liegen. Mannschaftsspiele und andere Events
werden unabhängig abgefragt und paginiert (`group=team_matches` bzw.
`group=other_events`). Der Gruppenfilter wird vor Zählung und Pagination angewandt.
Jede Liste hat eigene Trefferzahlen, Seiten, Ladezustände und Fehleranzeigen.
Ohne Gruppenparameter bleibt die kombinierte API-Abfrage verfügbar. Die Sichtbarkeit
des Events und `report_expected` begrenzen die manuelle Auswahl nicht. Letzteres
bleibt eine Regel für die automatische Generierung. Ein bereits selbst übernommener
Beitrag kann erneut vorbereitet werden; ein fremder zugeordneter Beitrag führt zu 409.

Eigene DRAFT- und IN_REVIEW-Beiträge bleiben bearbeitbar. Einreichen setzt IN_REVIEW;
weitere Änderungen belassen diesen Status. Veröffentlichte eigene Beiträge sind
für Berichteschreiber nur lesbar. Editoren und Admins dürfen veröffentlichte Inhalte
direkt korrigieren; die Änderungen sind sofort sichtbar. Es gibt keine Revisionen
oder Rückgabe zur Überarbeitung. Redaktion und Admins können Beiträge archivieren,
als Entwurf wiederherstellen oder löschen. Wiederherstellen veröffentlicht nicht
automatisch erneut. Beim Löschen bleiben Event, Tags und Medien erhalten; ein
zugehöriger Event steht anschließend wieder zur Berichterstellung zur Verfügung.

Titel und Slug sind bereits beim Speichern Pflicht. Der Teaser ist immer optional.
Inhalt darf im Entwurf leer sein, muss aber für IN_REVIEW und PUBLISHED gefüllt sein.
Neue Spielberichte erhalten ihren Slug aus Mannschaftsname, Mannschaftsnummer und
Spieldatum in Europe/Berlin, beispielsweise `herren-2-2026-09-17`. Titeländerungen
ändern diesen Link nicht. Bereits menschlich bearbeitete Artikel behalten ihre
bisherigen Links. Bei anderen Events lautet der vorbereitete Slug `bericht-{event_id}`.
Artikel zu Mannschaftsspielen haben zwingend MATCH_REPORT als Typ. MATCH_REPORT
kann im CMS nur mit einem solchen Event gespeichert werden. Die Eventzuordnung
ist nach dem ersten Speichern fest. Titel, Tags und Inhalt bleiben bearbeitbar.

Tags werden als Liste von Zeichenketten gespeichert, getrimmt, kleingeschrieben
und dedupliziert. Neue Tags werden bei Bedarf angelegt; es gibt noch keine eigene
Tag-Verwaltungsoberfläche. `cover_image_id` kann auf ein bereits vorhandenes
Medienobjekt verweisen. Medienupload, Dateiauslieferung und ein Medienkatalog bleiben
separate, geplante Funktionen. Artikelinhalt wird als Text gespeichert; ein
Rich-Text-Format und dessen sichere Darstellung sind noch nicht festgelegt.

## Gebündelte Use Cases

Für Galerien stellt `articles/public.py` einen kleinen Berichtskontext bereit:
Titelbild und Bearbeitbarkeit für den jeweiligen Schreiber. Der SQL-Adapter
`articles/gallery_reader.py` lädt und sperrt den Bericht, nachdem das Event
gesperrt wurde. Eigene Entwürfe und eingereichte Berichte sowie übernehmbare
Systementwürfe sind für Schreiber zulässig. Die Galerieanlage übernimmt keinen
Systembericht und synchronisiert spätere Titelbildänderungen noch nicht.

| Use Case | Aufgabe |
| --- | --- |
| `ListArticleOpportunities` | Schreibanlässe gruppiert und paginiert laden |
| `PrepareArticleForEvent` | Formular aus vorhandenem Artikel oder Event vorbereiten |
| `ListArticles` | Eigene, redaktionelle, öffentliche oder Mitgliederlisten laden |
| `GetArticle` | Einzelnen Artikel mit Zugriffsschutz und erlaubten Aktionen laden |
| `SaveArticle` | Neu erstellen, Systementwurf übernehmen oder bestehenden Beitrag speichern |
| `SubmitArticle` | Dieselben Speicherregeln verwenden und atomar einreichen |
| `PublishArticle` | Als Editor/Admin veröffentlichen und Zeitpunkt setzen |
| `ManageArticle` | Sichtbarkeit ändern, archivieren, als Entwurf wiederherstellen oder löschen |
| `CreateMatchReportDraft` | Automatischen Spielbericht idempotent erzeugen |

Die bisherigen Klassen `CreateArticle` und `EditArticleDraft` bleiben für vorhandene
interne Aufrufer und CLI-Kompatibilität erhalten. Der neue HTTP-Schreibpfad verwendet
`SaveArticle` beziehungsweise `SubmitArticle`. Auch der alte CLI-Editor erhält bei
Korrekturen menschlicher Beiträge den ursprünglichen Autor.

## HTTP-Vertrag

Basis der CMS-Endpunkte: `/api/admin/articles`.

| Methode und Pfad | Verwendung |
| --- | --- |
| `GET /opportunities` | Eventauswahl; `team_matches` und `other_events` |
| `GET /prepare/{event_id}` | Formularwerte, optionale Artikel-ID und `editable_fields` |
| `GET ?scope=mine` | Eigene Beiträge |
| `GET ?scope=editorial` | Alle Beiträge, nur EDITOR/ADMIN |
| `GET /{article_id}` | CMS-Detailansicht |
| `POST /save` | Erstellen oder inzwischen vorhandenen Systementwurf übernehmen |
| `PUT /{article_id}` | Vollständiges Formular speichern; auch Systementwurf übernehmen |
| `POST /submit` | Neues Formular atomar speichern und einreichen |
| `POST /{article_id}/submit` | Vorhandenen Beitrag speichern und einreichen |
| `POST /{article_id}/publish` | Gespeicherten Stand veröffentlichen, nur EDITOR/ADMIN |
| `PATCH /{article_id}/visibility` | Nur Sichtbarkeit ändern, nur EDITOR/ADMIN |
| `POST /{article_id}/archive` | Archivieren, nur EDITOR/ADMIN |
| `POST /{article_id}/restore` | Als DRAFT wiederherstellen, nur EDITOR/ADMIN |
| `DELETE /{article_id}` | Artikel und Tagzuordnungen löschen, nur EDITOR/ADMIN |
| `POST /` | Bestehender Erstellungsendpunkt mit kompakter Antwort bleibt kompatibel |

Listen unterstützen `offset`, `limit` (1–100), `article_type` und wiederholtes
`status`. CMS-Listen unterstützen außerdem `updated_since` (ISO-Zeitpunkt mit
Zeitzone, einschließlich Grenzwert). Der Filter wird vor Zählung und Pagination
angewendet. Die Redaktion startet im Reiter „Eingereicht“ ohne Zeitbegrenzung.
Eine zusätzliche Abfrage liefert die Gesamtzahl offener Einreichungen unabhängig
von Beitragsart und Zeitraum. Die weiteren Reiter „Entwürfe“, „Veröffentlicht“,
„Archiviert“ und „Alle“ zeigen standardmäßig die innerhalb der letzten 14 Tage
bearbeiteten Beiträge; 30 Tage, 90 Tage und der gesamte Zeitraum sind auswählbar.
„Meine Beiträge“ bleibt ohne Zeitbegrenzung. Beispiel für den Bereich „Entwürfe“:

```text
GET /api/admin/articles?scope=mine&status=DRAFT&status=IN_REVIEW&limit=20
```

CMS-Listen sind nach letzter Änderung, öffentliche Listen nach Veröffentlichung
absteigend sortiert, jeweils mit ID als stabilem zweiten Sortierkriterium.
Die Pagination der Schreibanlässe gilt über beide Eventgruppen gemeinsam.
Artikelantworten enthalten Autor-ID und Namen sowie `allowed_actions` (`save`,
`submit`, `publish`, `visibility`, `archive`, `restore`, `delete`). Ein leerer
Aktionssatz bedeutet eine reine Leseansicht. Direkte Listenaktionen übertragen nur
ihre jeweilige Änderung, damit sie keine veralteten Textinhalte zurückschreiben.

Schreibrequests enthalten Titel, Slug, Teaser, Inhalt, Typ, Sichtbarkeit, Tags,
optional `cover_image_id`, `event_id` oder bei erstmaliger freier Erstellung
`new_event`. PUT und Einreichen übertragen das vollständige Formular, einschließlich
vorhandener Event-ID und Tags. Weggelassene optionale Felder erhalten ihre Defaults.
Autor und Status werden vom Backend bestimmt. Das Veröffentlichungs-Endpoint
veröffentlicht den zuletzt gespeicherten Stand ohne Formulardaten im Request.

`new_event` benötigt Titel, Beginn mit Zeitzone und Kategorie-ID; Ende, Ort und
Beschreibung sind optional. Die Kategorie muss aktiv sein. Die vorhandene Abfrage
`GET /api/event-categories` liefert auswählbare manuelle Kategorien. Der neue Event
wird HIDDEN, seine Sichtbarkeit bestimmt nicht die des Artikels.

Öffentliche und interne Leseansichten verwenden dieselben Query-Use-Cases:

- `GET /api/articles` und `GET /api/articles/{slug}`: nur PUBLISHED + PUBLIC.
- `GET /api/intern/articles` und `GET /api/intern/articles/{slug}`:
  Anmeldung erforderlich; PUBLISHED + PUBLIC oder MEMBERS_ONLY.
- HIDDEN bleibt ausschließlich im berechtigten CMS sichtbar.

Öffentliche Antwortschemas enthalten keine internen Status-, Eigentümer-ID- oder
Aktionsfelder. Nicht lesbare Einzelartikel liefern 404. Fehlende Schreibrechte
liefern 403, Zuordnungs- und Slugkonflikte 409, ungültige Formularwerte 422.

## Architektur und Transaktionen

- `core/content/articles/domain`: Entity, Validierung und Statusübergänge.
- `application/commands.py`, `queries.py`, `dto.py`, `ports.py`, `access.py`:
  transportunabhängige Abläufe, Daten und Berechtigungsregeln.
- `adapters/inbound/http/articles`: Auth-Abbildung, Schemas, Router und Fehlerübersetzung.
- `adapters/outbound/persistence/articles`: Tabellen, Repository, Reader und Unit of Work.
- `adapters/outbound/articles/events.py`: Anbindung an den öffentlichen Events-Vertrag.
- `bootstrap/articles.py`: konkrete Verdrahtung.

Reads nutzen Projektionen über einen Reader-Port, keine schreibende Unit of Work.
Writes ändern Domain-Objekte und bestätigen erst anschließend die Transaktion.
`SubmitArticle` verwendet denselben Speicherablauf wie `SaveArticle`, einschließlich
Übernahme und optionalem Event. Die Event-Komponente stellt dafür über `events.public`
`CreateHiddenEditorialEvent` bereit: validieren und speichern, aber kein eigenes Commit.
Ein Fehler rollt Event, Artikel und Tagzuordnungen gemeinsam zurück.

Die optionale Eventerstellung im Berichtsformular verwendet die gemeinsame
Frontend-Komponente `shared/editorial-event/EditorialEvent`. Sie enthält Checkbox,
Eventfelder und das Laden der Kategorien einschließlich Fehleranzeige und Retry.
Der aufrufende Editor besitzt die FormGroup sowie den Aktivierungszustand und
übernimmt Speichern und den Schutz ungespeicherter Änderungen. Die gemeinsame
Formularhilfe validiert Titel, Kategorie und Zeitraum und konvertiert lokale
Datumswerte für den API-Request. Der Datentyp liegt unter `core/events`.

Der neutrale Backend-Vertrag liegt in `events/application/editorial_events.py`
und wird über `events.public` bereitgestellt. Er setzt weiterhin HIDDEN und
`report_expected=true`. Das Galerieformular verwendet dieselbe Komponente;
die Galerie-Transaktion bindet denselben Event-Anwendungsfall ein.

Pro Event ist höchstens ein Artikel erlaubt. Die Migration `c9e15f30a624` ergänzt
`uq_article_event_id`; freie Artikel mit NULL bleiben mehrfach möglich. Sie löscht
keine Inhalte und bricht bei bereits vorhandenen Mehrfachzuordnungen ab. Diese
müssen vor einem erneuten Upgrade fachlich geklärt werden.

Speicherung und automatische Generierung sperren die Eventzeile vor der Entscheidung,
ob ein Artikel existiert. Übernahmen sperren außerdem den Artikel und prüfen den
aktuellen Autor. So gewinnt bei konkurrierenden Benutzern nur eine Übernahme.
Generierung prüft nach dem Erzeugen des Textes erneut auf vorhandene Berichte und
überschreibt keine menschlichen Beiträge. Taganlage ist unter PostgreSQL ebenfalls
gegen gleichzeitige Anlage gesichert. Eventlöschung behält das bisherige SET NULL
am Artikel bei; diese Migration verändert das Löschverhalten nicht.

Normale Bearbeitungen werden serialisiert; es gibt noch keine Versionsnummer zur
Erkennung veralteter Formularstände. Der zuletzt erfolgreich gespeicherte Stand gilt.

## Prüfung

`tests/components/content/articles/test_cms.py` prüft den Rollen- und Statusablauf,
Vorbereitung, Übernahme, Sichtbarkeit, Pagination, Spielbindung, Tags/Titelbild und
atomare Eventanlage. Bestehende Artikel-, Auth- und Automatisierungstests bleiben aktiv.

`tests/test_article_cms_postgres.py` prüft in zufällig benannten Wegwerf-Datenbanken
Migration/Schemaabgleich, Upgrade mit Daten, Abbruch bei Duplikaten, konkurrierende
Übernahmen sowie Generierung während menschlicher Berichtserstellung. Wie die
Outbox-Tests benötigt es `TTC_TEST_POSTGRES_URL`; es verändert nicht die Anwendungsdatenbank.

## Frontend

Das Angular-Frontend implementiert „Neuer Beitrag“, „Meine Beiträge“, „Redaktion“
und einen gemeinsamen Editor. Eigene eingereichte Beiträge bleiben bis zur
Veröffentlichung bearbeitbar; veröffentlichte Beiträge erhalten eine Leseansicht.
Die Redaktion bietet Sichtbarkeit über ein Symbol mit beschrifteter Auswahl,
Veröffentlichung als Textbutton sowie Bearbeitung, Archivierung und Wiederherstellung
direkt in der Liste. Löschen steht unter „Weitere Aktionen“ und benötigt eine Bestätigung.

Öffentliche News und Mitgliederbeiträge verwenden die jeweiligen Leseendpunkte.
Ohne Teaser zeigt die Übersicht einen kurzen Inhaltsauszug. Inhalte werden als
Text ausgegeben. Medienupload und ein Rich-Text-Editor bleiben geplant.

Angular-Tests prüfen API-Verträge, Listen und Editorabläufe. Zusätzlich prüft
`frontend/scripts/check-articles.cjs` mit Playwright und Axe Desktop-/Mobilansichten
und zentrale Aktionen gegen eine simulierte API, ohne Anwendungsdaten zu ändern.


### Selecting report covers from an event gallery

The editor now embeds a gallery action beside the upload button. Saved reports
can create their event gallery with the shared multi-image uploader or select
an existing gallery image. Unsaved report changes must be saved before gallery
creation so the current stored cover can be adopted. Picking an image only
changes the form; the normal report save validates and persists the selection.
The media component grants contextual preview/caption reads for editable
reports without extending gallery editing rights. The article repository uses
the public media persistence contract to validate foreign uploads against the
actual, immutable event association. Changed, non-empty report covers are adopted
into an existing event gallery through the `ArticleGalleryCovers` port in the
same unit of work: append once, then set as gallery cover. The SQL bridge calls
media's public contract, preserving the event/report/gallery lock order. Failure
rolls back both changes; updated gallery versions reject stale forms. No gallery
is created implicitly, and removing the report cover does not remove gallery
images or its cover. See `media-architecture.md` for details.
