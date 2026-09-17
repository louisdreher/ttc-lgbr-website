class ArticleApplicationError(ValueError):
    """Base class for article application errors."""


class ArticleNotFoundError(ArticleApplicationError):
    pass


class ReportNotReadyError(ArticleApplicationError):
    pass


class ArticleAuthorError(ArticleApplicationError):
    pass


class ArticleConflictError(ArticleApplicationError):
    pass


class ArticleSlugAlreadyExistsError(ArticleApplicationError):
    def __init__(self, slug: str):
        super().__init__(f"Ein Artikel mit dem Slug '{slug}' existiert bereits.")
