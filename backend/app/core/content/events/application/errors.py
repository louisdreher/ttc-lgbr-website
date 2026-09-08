from app.core.content.events.domain.errors import EventServiceError


class EventNotFoundError(EventServiceError):
    pass


class EventCategoryNotFoundError(EventServiceError):
    pass


class EventCategorySlugConflictError(EventServiceError):
    pass
