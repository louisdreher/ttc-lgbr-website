from uuid import uuid4

from app.core.content.articles.application.access import require_editor, require_writer
from app.core.content.articles.application.dto import (
    CreateMatchReportDraftCommand,
    EditArticleDraftCommand,
    ManageArticleCommand,
    MatchReportDraftResult,
    PublishArticleCommand,
    SaveArticleCommand,
)
from app.core.content.articles.application.errors import (
    ArticleAuthorError,
    ArticleConflictError,
    ArticleNotFoundError,
    ArticleSlugAlreadyExistsError,
    ReportNotReadyError,
)
from app.core.content.articles.application.ports import (
    ArticleAuthors,
    ArticleEvents,
    ArticleUnitOfWork,
    MatchReportGenerator,
    MatchReportReader,
)
from app.core.content.articles.domain.article import (
    Article,
    ArticleStatus,
    ArticleType,
    utc_now,
)
from app.core.content.articles.domain.errors import ArticleDomainError
from app.core.content.articles.domain.slugs import match_report_slug


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
            if data.event_id is not None:
                self.uow.articles.lock_event(data.event_id)
            existing = self.uow.articles.find_match_report(key, data.event_id)
            if existing is not None:
                return MatchReportDraftResult(existing.id, False, "already_exists")
            author_id = (
                command.author_id
                if command.author_id is not None
                else self.authors.system_id()
            )
            slug = match_report_slug(
                data.match.team_name, data.match.team_number, data.match.scheduled_at
            )
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
                author_id=(
                    command.author_id
                    if article.author_id == self.authors.system_id()
                    else article.author_id
                ),
                title=command.title,
                teaser=command.teaser,
                content=command.content,
            )
            self.uow.articles.save(article)
            self.uow.commit()


class SaveArticle:
    def __init__(
        self, uow: ArticleUnitOfWork, authors: ArticleAuthors, events: ArticleEvents
    ):
        self.uow, self.authors, self.events = uow, authors, events

    def execute(self, command: SaveArticleCommand) -> int:
        return self._execute(command, submit=False)

    def _execute(self, command: SaveArticleCommand, *, submit: bool) -> int:
        require_writer(command.actor)
        with self.uow:
            event_id = command.event_id
            if command.new_event is not None:
                if event_id is not None or command.article_id is not None:
                    raise ArticleDomainError(
                        "Ein neuer Event ist nur bei einem "
                        "neuen freien Beitrag möglich."
                    )
                event_id = self.events.create_hidden(
                    command.new_event, command.actor.user_id
                )
            context = self.events.get(event_id) if event_id is not None else None
            # Event lock precedes the article lock, also in automatic generation.
            if event_id is not None:
                self.uow.articles.lock_event(event_id)
            article = (
                self.uow.articles.get(command.article_id, for_update=True)
                if command.article_id is not None
                else None
            )
            if command.article_id is not None and article is None:
                raise ArticleNotFoundError("Beitrag nicht gefunden.")
            if article is not None and article.event_id != event_id:
                raise ArticleDomainError(
                    "Die Eventzuordnung eines gespeicherten Beitrags ist fest."
                )
            existing = (
                self.uow.articles.find_by_event(event_id)
                if event_id is not None
                else None
            )
            if article is None and existing is not None:
                article = self.uow.articles.get(existing.id, for_update=True)
                if article.author_id != self.authors.system_id():
                    raise ArticleConflictError(
                        "Für diesen Event wurde bereits ein Beitrag übernommen."
                    )
            taking_over = False
            if article is not None:
                system = article.author_id == self.authors.system_id()
                if (
                    system
                    and article.status != ArticleStatus.DRAFT
                    and not command.actor.can_edit_all
                ):
                    raise ArticleConflictError(
                        "Dieser Systembeitrag ist nicht mehr übernehmbar."
                    )
                if not command.actor.can_edit_all:
                    if article.status not in (
                        ArticleStatus.DRAFT,
                        ArticleStatus.IN_REVIEW,
                    ):
                        raise ArticleAuthorError(
                            "Veröffentlichte Beiträge sind nur lesbar."
                        )
                    if not system and article.author_id != command.actor.user_id:
                        raise ArticleAuthorError(
                            "Nur eigene Beiträge dürfen bearbeitet werden."
                        )
                if system and article.status == ArticleStatus.DRAFT:
                    taking_over = True
                    article.author_id = command.actor.user_id
            if context is not None and context.team_match_id is not None:
                if command.article_type != ArticleType.MATCH_REPORT:
                    raise ArticleDomainError(
                        "Für Mannschaftsspiele ist der Berichtstyp MATCH_REPORT fest."
                    )
            elif command.article_type == ArticleType.MATCH_REPORT:
                raise ArticleDomainError(
                    "Ein Spielbericht benötigt ein Mannschaftsspiel als Event."
                )
            slug = command.slug.strip().lower()
            if context is not None and context.match_slug is not None:
                # Preserve existing human-authored addresses and published links.
                slug = (
                    article.slug
                    if article is not None and not taking_over
                    else context.match_slug
                )
            if (
                article is None or slug != article.slug
            ) and self.uow.articles.slug_exists(slug):
                raise ArticleSlugAlreadyExistsError(slug)
            if article is None:
                now = utc_now()
                article = Article(
                    id=None,
                    author_id=command.actor.user_id,
                    title=command.title,
                    slug=slug,
                    teaser=command.teaser,
                    content=command.content,
                    article_type=command.article_type,
                    visibility=command.visibility,
                    status=ArticleStatus.DRAFT,
                    event_id=event_id,
                    published_at=None,
                    created_at=now,
                    updated_at=now,
                )
            cover_changed = command.cover_image_id != article.cover_image_id
            if cover_changed:
                self.uow.articles.validate_cover(
                    command.cover_image_id,
                    user_id=command.actor.user_id,
                    can_edit_all=command.actor.can_edit_all,
                    event_id=article.event_id,
                )
            article.revise(
                title=command.title,
                slug=slug,
                teaser=command.teaser,
                content=command.content,
                article_type=command.article_type,
                visibility=command.visibility,
                tags=list(command.tags),
                cover_image_id=command.cover_image_id,
            )
            if submit:
                article.submit()
            saved = self.uow.articles.save(article)
            if saved.id is None:
                raise RuntimeError("Der gespeicherte Beitrag besitzt keine ID.")
            if cover_changed and saved.event_id is not None and saved.cover_image_id is not None:
                self.uow.gallery_covers.adopt(saved.event_id, saved.cover_image_id)
            self.uow.commit()
            return saved.id


class SubmitArticle(SaveArticle):
    def execute(self, command: SaveArticleCommand) -> int:
        return self._execute(command, submit=True)


class PublishArticle:
    def __init__(self, uow: ArticleUnitOfWork):
        self.uow = uow

    def execute(self, command: PublishArticleCommand) -> int:
        require_editor(command.actor)
        with self.uow:
            article = self.uow.articles.get(command.article_id, for_update=True)
            if article is None:
                raise ArticleNotFoundError("Beitrag nicht gefunden.")
            article.publish()
            self.uow.articles.save(article)
            self.uow.commit()
            return article.id


class ManageArticle:
    """Apply narrow editorial changes to a freshly locked article."""

    def __init__(self, uow: ArticleUnitOfWork):
        self.uow = uow

    def execute(self, command: ManageArticleCommand) -> None:
        require_editor(command.actor)
        with self.uow:
            # Same event-before-article lock order as save and generation.
            current = self.uow.articles.get(command.article_id)
            if current is None:
                raise ArticleNotFoundError("Beitrag nicht gefunden.")
            if current.event_id is not None:
                self.uow.articles.lock_event(current.event_id)
            article = self.uow.articles.get(command.article_id, for_update=True)
            if article is None:
                raise ArticleNotFoundError("Beitrag nicht gefunden.")
            if command.action == "delete":
                self.uow.articles.delete(article)
            else:
                if command.action == "visibility" and command.visibility is not None:
                    article.change_visibility(command.visibility)
                elif command.action == "archive":
                    article.archive()
                elif command.action == "restore":
                    article.restore()
                else:
                    raise ArticleDomainError("Ungültige Redaktionsaktion.")
                self.uow.articles.save(article)
            self.uow.commit()
