from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.inbound.http.events.dependencies import (
    provide_list_public_event_categories,
    provide_list_public_events,
)
from app.adapters.inbound.http.events.schemas import (
    PublicEventCategoryRead,
    PublicEventRead,
)
from app.core.content.events.application.dto import ListPublicEventsQuery
from app.core.content.events.application.queries import (
    ListPublicEventCategories,
    ListPublicEvents,
)
from app.core.content.events.domain.errors import EventServiceError

router = APIRouter(prefix="/api", tags=["Public events"])


@router.get("/event-categories", response_model=list[PublicEventCategoryRead])
def get_public_event_categories(
    *,
    list_public_event_categories_use_case: Annotated[
        ListPublicEventCategories, Depends(provide_list_public_event_categories)
    ],
) -> list[PublicEventCategoryRead]:
    return list_public_event_categories_use_case.execute()


@router.get("/events", response_model=list[PublicEventRead])
def get_public_events(
    *,
    list_public_events_use_case: Annotated[
        ListPublicEvents, Depends(provide_list_public_events)
    ],
    starts_from: datetime,
    starts_until: datetime,
    category_id: Annotated[list[int] | None, Query()] = None,
) -> list[PublicEventRead]:
    try:
        return list_public_events_use_case.execute(
            ListPublicEventsQuery(
                starts_from=starts_from,
                starts_until=starts_until,
                category_ids=category_id,
            )
        )
    except EventServiceError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
