class ArticleDomainError(ValueError):
    """Base class for invalid article-domain operations."""


class EmptyArticleFieldError(ArticleDomainError):
    def __init__(self, field_name: str):
        super().__init__(f"{field_name} darf nicht leer sein.")
