# Articles: vorhandene Entwurfserstellung

Articles folgt für den vorhandenen Anwendungsfall dem Events-Muster.
Der Umfang bleibt die Erstellung eines Artikelentwurfs. Neue Lese-, Bearbeitungs-
oder Veröffentlichungsfunktionen wurden nicht ergänzt.

## Aufbau

- `core/content/articles/domain`: Artikel-Entity, fachliche Typen und Validierung.
- `application/dto.py`: `CreateArticleCommand` und `CreatedArticle`.
- `application/create_article.py`: Klasse `CreateArticle` mit `execute(command)`.
- `application/ports.py`: `ArticleRepository` und `ArticleUnitOfWork`.
- `adapters/inbound/http/articles`: Request/Response, Router und FastAPI-Dependencies.
- `adapters/outbound/persistence/articles/models.py`: SQLModel-Tabellen für
  Artikel, Tags und deren Zuordnung.
- `repository.py`: Übersetzung zwischen Domain und Tabellenmodell; speichert
  mit `flush()` innerhalb der Transaktion, führt kein Commit aus.
- `unit_of_work.py`: Commit und Rollback über die gemeinsame Session.
- `bootstrap/articles.py`: verbindet die konkrete Unit of Work mit dem Usecase.

## Ablauf

Der HTTP-Router erhält den Usecase über `provide_create_article`. Die Dependency
übergibt die Session des Requests an `build_create_article(session)` im Bootstrap.
Die Benutzer-ID wird aus der Anmeldung übernommen; sie stammt nicht aus dem
Request-Body. ADMIN und EDITOR dürfen weiterhin Entwürfe erstellen.

`CreateArticle.execute(command)` erstellt über `Article.create_draft` einen
validierten Entwurf, prüft die Verfügbarkeit des Slugs und speichert über das
Repository. Die Unit of Work bestätigt die Transaktion erst, wenn ein gültiges
Ergebnis mit ID vorliegt. Bei einem Fehler wird zurückgerollt. Die Session selbst
wird vom Aufrufer beziehungsweise von der Request-Dependency geschlossen.

Tag-Verwaltung und Titelbilder haben bisher nur Tabellenmodelle; hierfür wurden
keine künstlichen Domain-Services eingeführt. Die bereits vorhandenen getrennten
Domain- und Persistenz-Enums bleiben über das Repository abgebildet.

## Prüfung

Alle Backend-Tests werden aus `backend/` mit `python -m pytest` ausgeführt.
Die Article-Tests prüfen Entwurfsnormalisierung, Slug-Konflikte, HTTP-Antworten,
die angemeldete Autorenschaft und Rollback nach Flush. Ein Import-Test hält
Framework- und Adapter-Abhängigkeiten aus dem Article-Core heraus.

Tabellen, Indizes, Enum-Werte und der OpenAPI-Vertrag wurden vor und nach dem
Umbau verglichen und sind unverändert. Keine Migration ist erforderlich.
Die Tests verwenden SQLite; ein Live-PostgreSQL-Test wurde nicht ausgeführt.
