"""Compatibility import for the relocated content article model."""

from app.domains.content.articles.model import (
    Article,
    ArticleStatus,
    ArticleTag,
    ArticleType,
    Tag,
)

__all__ = ["Article", "ArticleStatus", "ArticleTag", "ArticleType", "Tag"]
