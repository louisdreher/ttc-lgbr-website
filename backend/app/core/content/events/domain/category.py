from dataclasses import dataclass

from app.core.content.events.domain.errors import (
    EventCategoryInactiveError,
    EventServiceError,
)
from app.core.content.events.domain.event import reject_nulls, required_text

TEAM_MATCH_CATEGORY_SLUG = "mannschaftsspiel"
TEAM_MATCH_CATEGORY_NAME = "Mannschaftsspiel"


@dataclass(kw_only=True)
class EventCategory:
    name: str
    slug: str
    id: int | None = None
    default_report_expected: bool = False
    is_active: bool = True
    sort_order: int = 0

    @classmethod
    def create(cls, **values) -> "EventCategory":
        category = cls(**values)
        category.name = required_text(category.name, "Der Kategoriename")
        category.slug = required_text(category.slug, "Der Slug").lower()
        return category

    def ensure_active(self) -> None:
        if not self.is_active:
            raise EventCategoryInactiveError(
                "Deaktivierte Event-Kategorien können nicht verwendet werden."
            )

    def edit(self, changes: dict) -> None:
        changes = dict(changes)
        allowed = {"name", "slug", "default_report_expected", "is_active", "sort_order"}
        if set(changes) - allowed:
            raise EventServiceError("Unbekannte Kategorie-Felder.")
        reject_nulls(changes, allowed)
        if "name" in changes:
            changes["name"] = required_text(changes["name"], "Der Kategoriename")
        if "slug" in changes:
            changes["slug"] = required_text(changes["slug"], "Der Slug").lower()
        for name, value in changes.items():
            setattr(self, name, value)
