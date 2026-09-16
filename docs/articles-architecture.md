# Articles: Entwurfserstellung und Spielberichte

Articles folgt für den vorhandenen Anwendungsfall dem Events-Muster.
Neben der bisherigen HTTP-Entwurfserstellung gibt es jetzt die Backend-Usecases
`CreateMatchReportDraft` und `EditArticleDraft` in `application/commands.py`.
Die neuen Usecases sind direkt über Bootstrap aufrufbar; neue
HTTP-Endpunkte oder Veröffentlichungsfunktionen wurden nicht ergänzt.
Der vollständige Ablauf ist unter [Content-Automation](content-automation.md) beschrieben.

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

Der OpenAPI-Vertrag bleibt unverändert. Migration `f3b82e0a7c51` ergänzt
Generierungsherkunft, einen eindeutigen Generierungsschlüssel, den Systemautor
und Outbox-Verarbeitungsfelder. PostgreSQL-Tests prüfen Schemaabgleich und
gleichzeitige Berichtsanfragen; SQLite-Tests prüfen den vollständigen Ablauf
einschließlich Autorenwechsel und Schutz redaktioneller Änderungen.
