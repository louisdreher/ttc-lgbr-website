# Events: DDD und Ports und Adapters im Projekt

Die Events-Komponente ist in Domain, Application und Adapter getrennt.
Die vorhandenen Endpunkte, Tabellen und Enum-Werte bleiben bestehen.
`Event` bezeichnet hier einen Vereinstermin, kein technisches Domain Event.
Ein Event-Bus wurde nicht eingeführt.

## Aufbau

```text
backend/app/
  core/content/events/
    domain/
      event.py            Event-Entity, Status, Zeitraum und Bearbeitungsregeln
      category.py         EventCategory, Aktivierung und Normalisierung
      errors.py           Fachliche Fehler
    application/
      dto.py              Eingaben und Ergebnisse ohne Pydantic oder SQLModel
      commands.py         Schreibende Usecase-Klassen mit execute(command)
      queries.py          Lesende Usecase-Klassen mit execute(query)
      ports.py            Repository-, Reader- und Unit-of-Work-Verträge
      sync_match.py       Mannschaftsspiel als Event übernehmen
      errors.py           Nicht gefunden und Slug-Konflikt
    public.py             Öffentlicher Vertrag für Spielimporte
  bootstrap/
    events.py             Usecases mit konkreten SQL-Adaptern zusammenbauen
  adapters/
    inbound/
      http/events/
        admin_router.py   Geschützte Verwaltungsendpunkte
        public_router.py  Öffentliche Kalenderendpunkte
        schemas.py        Pydantic-Request- und Response-Modelle
        dependencies.py   Bootstrap-Factories an FastAPI-Requests anbinden
      competition/
        events.py         Bestehenden Spielimport an Events anbinden
    outbound/persistence/events/
      models.py           SQLModel-Tabellenmodelle
      repository.py       Domain-Entities laden und speichern
      reader.py           Abfragen und Ergebnisprojektionen
      unit_of_work.py     Commit und Rollback für Schreib-Usecases
```

## Beispiel: Einen Termin anlegen

1. `admin_router.py` prüft weiterhin über die bestehende Auth-Dependency die
   Rollen ADMIN oder EDITOR. Pydantic prüft das HTTP-Format.
2. Der Router übersetzt `EventCreate` in das Application-Datenobjekt
   `CreateEventCommand`. Die Benutzer-ID kommt aus der Anmeldung, nicht aus dem Body.
3. `CreateEvent.execute(command)` lädt über den Kategorie-Port die Kategorie und
   prüft, ob sie aktiv ist. Fehlt eine explizite Berichtserwartung, übernimmt
   der Usecase deren Standardwert.
4. `Event.create` normalisiert den Titel und prüft den Zeitraum. Dafür braucht
   die Domain weder FastAPI noch eine Datenbank.
5. Das Repository übersetzt die Entity in das SQLModel-Tabellenmodell.
   `flush()` schreibt innerhalb der laufenden Transaktion und liefert die ID.
6. Der Usecase ruft `uow.commit()` auf. Bei einem Fehler wird zurückgerollt.
7. Der Router liest das Ergebnis über `GetEvent.execute(GetEventQuery(...))`, einschließlich des
   Erstellernamens. Das HTTP-Response-Modell bestimmt die ausgegebenen Felder.

Jeder Usecase ist eine eigene Klasse. Abhängigkeiten wie `EventUnitOfWork` oder
`EventReader` werden im Konstruktor übergeben; Eingaben für einen einzelnen
Aufruf kommen in `execute`. Es gibt keine gemeinsame Usecase-Basisklasse und
keinen Command-Bus. Die Klassen bleiben in `commands.py`, `queries.py` und
`sync_match.py` nach ihrer Aufgabe gruppiert.

Die Eingaben sind frameworkfreie Dataclasses in `dto.py`: schreibende Aufrufe
verwenden beispielsweise `CreateEventCommand` oder `UpdateEventCommand`, lesende
Aufrufe `GetEventQuery` oder `ListEventsQuery`. Die ID eines zu bearbeitenden
Events und die Benutzer-ID beim Erstellen gehören ebenfalls zur jeweiligen
Eingabe. Abfragen ohne Eingaben, etwa `ListEventYears`, verwenden `execute()`
ohne leeres Query-Objekt.

```python
use_case = CreateEvent(uow)
event = use_case.execute(
    CreateEventCommand(
        title="Vereinsausflug",
        starts_at=starts_at,
        category_id=category_id,
        created_by_user_id=current_user_id,
    )
)
```

## Infrastruktur und Verdrahtung

`bootstrap/events.py` ist die Composition Root für Events. Beispielsweise baut
`build_create_event(session)` eine `SqlEventUnitOfWork` mit ihren Repositories
und übergibt sie an `CreateEvent`. Die Factory enthält kein FastAPI-`Depends`.

`adapters/inbound/http/events/dependencies.py` beschafft über `Depends(get_session)`
die Session des aktuellen Requests und ruft die passende Bootstrap-Factory auf.
Der Router bekommt beispielsweise über `Depends(provide_create_event)` einen
fertigen `CreateEvent`-Usecase. Bei mehreren Dependencies desselben Requests
verwendet FastAPI dieselbe gecachte Session; die Factories erzeugen keine
globalen Session- oder Usecase-Singletons.

Bootstrap verbindet den Competition-Import über `CompetitionMatchEvents` mit
dem Events-Usecase und übergibt dieselbe Session für beide Schreibvorgänge.
Application und Domain importieren weder Bootstrap noch konkrete SQL-Adapter.

## Domain-Modell und Tabellenmodell

`domain.event.Event` ist eine Python-Dataclass mit fachlichem Verhalten.
`persistence.events.models.Event` beschreibt Tabellen, Fremdschlüssel,
Indizes und SQL-Typen. Das Repository übersetzt zwischen beiden.

Die Factory `Event.create` prüft neue Termine. Der normale Dataclass-Konstruktor
dient auch der Wiederherstellung gespeicherter Daten. Änderungen erfolgen in
den Usecases über Domain-Methoden wie `edit` und `ensure_deletable`.

Event und Kategorie haben eigene Identitäten und werden separat gespeichert.
Ein Event referenziert seine Kategorie über deren ID. Es lädt keinen vollständigen
Kategorie-Objektgraphen. Zusätzliche Value Objects sind derzeit nicht erforderlich.

## Teilupdates und Lesezugriffe

Bei PATCH wird `model_dump(exclude_unset=True)` an der HTTP-Grenze in ein
Application-Update übersetzt. Ein fehlender Schlüssel bedeutet „unverändert“,
ein vorhandener Schlüssel mit `None` bedeutet „explizit leeren“. Die Domain
begrenzt die zulässigen Felder und verbietet `None` für Pflichtfelder.

Die Update-DTOs verwenden dafür bewusst ein einfaches Änderungsdictionary.
Ein eigenes typisiertes Patch-Modell pro Feld wäre eine spätere Alternative,
falls die Zahl der Aufrufer oder die Regeln dafür deutlich wachsen.

Lesezugriffe verwenden einen separaten Reader-Port. Event-Listen liefern
`EventDetails`-DTOs ohne Domain-Objekte aufzubauen. Kleine Kategorie-Listen
geben die frameworkfreien Kategorie-Dataclasses zurück. Öffentliche Antworten
werden durch eigene HTTP-Schemas auf öffentliche Felder beschränkt.
Filterverhalten und Sortierung entsprechen den bisherigen Abfragen.

## Transaktionen und Mannschaftsspiele

Die Unit of Work besitzt die Transaktionsgrenze für manuelle Schreiboperationen.
Ein Sammellöschen prüft zunächst alle Events. Ein Fehler bei einer späteren
Speicherung rollt auch bereits geflushte Änderungen zurück. Die HTTP-Dependency
besitzt die Session und schließt sie am Ende des Requests.

Der Competition-Import ruft seinen ausgehenden `MatchEvents`-Port auf.
`CompetitionMatchEvents` baut aus den gespeicherten Competition-Modellen ein
`SyncMatchEventCommand`. Der separate Backfill verwendet den Application-Usecase
`BackfillMatchEvents.execute(command)` und denselben ausgehenden Adapter.
Der öffentliche Vertrag `events.public` stellt dieses Command und die Klasse
`SyncMatchEvent` bereit. Der Adapter ruft deren `execute(command)` auf.
Im Application-Core gibt es keine Imports von `TeamMatch`, `Team` oder SQLModel.

Die Synchronisierung führt **kein Commit** aus: Mannschaftsspiel, gegebenenfalls
neu angelegte Kategorie und Event gehören zur Transaktion des Imports.
Die Zuordnung bleibt über die eindeutige `team_match_id` idempotent.
Beschreibung, Sichtbarkeit und Berichtserwartung eines vorhandenen Events
bleiben erhalten. Historische Endzeiten vor dem Spielbeginn werden weiterhin
ignoriert. Auch das Backfill-Skript benutzt diesen Adapter.

## Bewusste Übergangsstellen

- Competition-Imports verwenden inzwischen eigene Usecases und Ports.
  Die ORM-Modelle liegen unter `adapters/outbound/persistence/competition`;
  ausschließlich Adapter und Composition greifen darauf zu. Der Core enthält
  die fachlichen Importtypen und Regeln.
- Die Reader-Projektion bezieht Erstellernamen über `users.public.UserReader`.
  Bootstrap injiziert den `SqlUserReader`; Events importiert keine User-ORM-Modelle.
- `Visibility` bleibt der bereits vorhandene kleine, frameworkfreie Content-Typ.
- Authentifizierung und Rollenprüfung liegen inzwischen im HTTP-Auth-Adapter.
  Der öffentliche Users-Vertrag liefert Rollen und Benutzer-DTOs ohne Passwortdaten.

## Verhalten und Prüfung

Zwei ungültige Eingaben liefern jetzt einen gezielten HTTP-422-Fehler:
`is_all_day: null` und öffentliche Datumsgrenzen, bei denen nur eine Grenze
eine Zeitzone enthält. Zuvor konnten diese zu technischen Fehlern führen.

Backend-Tests aus dem Verzeichnis `backend` ausführen:

```text
python -m pytest
```

Die Tests decken Domain-Regeln, einen Usecase mit In-Memory-Ports,
Persistenz, HTTP, Teilupdates, Sammeloperationen, Import-Idempotenz und Rollbacks
ab. Ein Import-Test schützt die Abhängigkeitsrichtung im Core.
Die Datenbanktests verwenden SQLite; sie ersetzen keinen PostgreSQL-Integrationstest.
Tabellenstruktur und Migrationen wurden bei diesem Umbau nicht geändert.
Der vollständige Events-OpenAPI-Vertrag und die generierten PostgreSQL-Definitionen
für Tabellen, Indizes und Enums wurden mit dem vorherigen Stand verglichen:
Sie sind identisch. Ein Test gegen eine laufende PostgreSQL-Datenbank wurde
für diesen Umbau nicht ausgeführt.
