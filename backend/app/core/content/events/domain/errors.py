class EventServiceError(ValueError):
    """Expected event validation failure; translated to HTTP by the adapter."""


class EventCategoryInactiveError(EventServiceError):
    pass


class SyncedEventFieldError(EventServiceError):
    pass


class SyncedEventDeleteError(EventServiceError):
    pass
