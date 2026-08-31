# Neue Website des TTC Langen-Brombach

Dieses Repository enthält die neue Vereinswebsite des TTC Langen-Brombach.
Sie verbindet einen modernen öffentlichen Auftritt mit einem internen Bereich
und einem eigenen Content-Management-System (CMS).

Das Projekt verfolgt zwei Ziele: Zum einen soll es die redaktionelle und
administrative Vereinsarbeit vereinfachen und wiederkehrende Abläufe möglichst
automatisieren. Zum anderen dient es als praxisnahes Lernprojekt für die
Entwicklung einer vollständigen Webanwendung – vom Frontend über API und
Datenmodell bis zu Migrationen und externen Integrationen.

## Schwerpunkte

- öffentliche Vereinsinformationen, Nachrichten, Mannschaften und Termine;
- geschützte Bereiche für Mitglieder und berechtigte Funktionsträger;
- ein rollenbasiertes CMS für Termine und zukünftig weitere Inhalte;
- Übernahme und Synchronisation von Spielplan-, Mannschafts- und
  Ergebnisdaten aus myTischtennis;
- Verknüpfung von Terminen, Mannschaftsspielen, Berichten und Medien, um
  redaktionelle Arbeitsschritte künftig gezielt vorzubereiten und zu
  automatisieren;
- geplante KI-Unterstützung, beispielsweise zur Erzeugung redaktionell
  prüfbarer Entwürfe für Spiel- und Veranstaltungsberichte über die OpenAI API;
- geplante Übernahme von Terminen aus PDF-Dokumenten, um manuelle
  Erfassungsarbeit weiter zu reduzieren.

## Aktueller Stand

Die Anwendung befindet sich in aktiver Entwicklung. Bereits vorhanden sind
unter anderem die grundlegende Seiten- und Bereichsstruktur, Authentifizierung
und Rollen, ein öffentliches Terminmodul, die Terminverwaltung im CMS sowie
die Datenmodelle und Synchronisationslogik für den Spielbetrieb.

Der vollständige Artikel- und Medienworkflow, KI-gestützte Berichtsentwürfe,
der Terminimport aus PDF-Dokumenten, automatisierte Hintergrundläufe und
weitere Verwaltungsfunktionen sind geplant beziehungsweise noch im Aufbau.
Der jeweilige Umsetzungsstand ist in der technischen Dokumentation ausdrücklich
gekennzeichnet.

## Technologien

- Angular und TypeScript
- FastAPI und Python
- PostgreSQL, SQLModel und Alembic
- Docker Compose

## Projektstruktur

```text
frontend/       Angular-Anwendung
backend/        FastAPI-Anwendung, Domänenlogik und Migrationen
docs/           Architektur- und Entwicklungsdokumentation
compose.yaml    lokale PostgreSQL-Infrastruktur
```

## Dokumentation

- [Architektur](docs/architecture.md)
- [Datenmodell](docs/data-model.md)
- [Entwicklungsumgebung und Prüfungen](docs/development.md)
- [Bekannte Einschränkungen und geplante Arbeiten](docs/known-issues.md)
- [Architekturentscheidungen](docs/decisions/README.md)
