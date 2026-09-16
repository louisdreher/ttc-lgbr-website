from uuid import uuid4

from app.core.content.articles.application.dto import (
    CreateMatchReportDraftCommand,
    EditArticleDraftCommand,
    MatchReportDraftResult,
)
from app.core.content.articles.application.errors import (
    ArticleNotFoundError,
    ReportNotReadyError,
)
from app.core.content.articles.application.ports import (
    ArticleAuthors,
    ArticleUnitOfWork,
    MatchReportGenerator,
    MatchReportReader,
)
from app.core.content.articles.domain.article import Article, ArticleType, utc_now


class CreateMatchReportDraft:
    def __init__(
        self,
        uow: ArticleUnitOfWork,
        reader: MatchReportReader,
        generator: MatchReportGenerator,
        authors: ArticleAuthors,
    ):
        self.uow, self.reader, self.generator, self.authors = (
            uow,
            reader,
            generator,
            authors,
        )

    def execute(self, command: CreateMatchReportDraftCommand) -> MatchReportDraftResult:
        if command.team_match_id <= 0:
            raise ValueError("Eine gültige Spiel-ID ist erforderlich.")
        key = f"team-match:{command.team_match_id}"
        with self.uow:
            if command.author_id is not None:
                self.authors.ensure_editor(command.author_id)
            existing = self.uow.articles.find_match_report(key, None)
            if existing is not None:
                return MatchReportDraftResult(existing.id, False, "already_exists")
        data = self.reader.read(command.team_match_id)
        if command.require_report_expected:
            if data.event_id is None:
                raise ReportNotReadyError("Der Kalendertermin zum Spiel fehlt.")
            if not data.report_expected:
                return MatchReportDraftResult(None, False, "report_not_expected")
        if not data.match.details_available or not data.match.is_completed:
            raise ReportNotReadyError(
                "Abgeschlossene Spielergebnisse sind noch nicht importiert."
            )

        # Keep a future slow generator outside the database write transaction.
        generated = self.generator.generate(data)
        with self.uow:
            self.uow.articles.lock_generation(command.team_match_id)
            existing = self.uow.articles.find_match_report(key, data.event_id)
            if existing is not None:
                return MatchReportDraftResult(existing.id, False, "already_exists")
            author_id = (
                command.author_id
                if command.author_id is not None
                else self.authors.system_id()
            )
            slug = f"spielbericht-{command.team_match_id}"
            if self.uow.articles.slug_exists(slug):
                slug = f"{slug}-{uuid4().hex}"
            article = Article.create_draft(
                author_id=author_id,
                title=generated.title,
                slug=slug,
                teaser=generated.teaser,
                content=generated.content,
                article_type=ArticleType.MATCH_REPORT,
                visibility=data.visibility,
                event_id=data.event_id,
            )
            article.generation_key = key
            article.generation_method = generated.method
            article.generated_at = utc_now()
            saved = self.uow.articles.save(article)
            if saved.id is None:
                raise RuntimeError("Der gespeicherte Bericht besitzt keine ID.")
            self.uow.commit()
            return MatchReportDraftResult(saved.id, True, "created")


class EditArticleDraft:
    def __init__(self, uow: ArticleUnitOfWork, authors: ArticleAuthors):
        self.uow, self.authors = uow, authors

    def execute(self, command: EditArticleDraftCommand) -> None:
        with self.uow:
            self.authors.ensure_editor(command.author_id)
            article = self.uow.articles.get(command.article_id, for_update=True)
            if article is None:
                raise ArticleNotFoundError("Der Artikel wurde nicht gefunden.")
            article.edit_draft(
                author_id=command.author_id,
                title=command.title,
                teaser=command.teaser,
                content=command.content,
            )
            self.uow.articles.save(article)
            self.uow.commit()
