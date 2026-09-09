from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.adapters.inbound.http.auth.permissions import require_any_role
from app.adapters.inbound.http.events.dependencies import (
    provide_create_event,
    provide_create_event_category,
    provide_delete_event,
    provide_delete_events,
    provide_get_event,
    provide_get_events,
    provide_list_event_categories,
    provide_list_event_years,
    provide_list_events,
    provide_update_event,
    provide_update_event_category,
    provide_update_events_visibility,
)
from app.adapters.inbound.http.events.schemas import (
    EventBulkVisibilityUpdate,
    EventCategoryCreate,
    EventCategoryRead,
    EventCategoryUpdate,
    EventCreate,
    EventIds,
    EventRead,
    EventUpdate,
)
from app.core.content.events.application.commands import (
    CreateEvent,
    CreateEventCategory,
    DeleteEvent,
    DeleteEvents,
    UpdateEvent,
    UpdateEventCategory,
    UpdateEventsVisibility,
)
from app.core.content.events.application.dto import (
    CreateEventCategoryCommand,
    CreateEventCommand,
    DeleteEventCommand,
    DeleteEventsCommand,
    GetEventQuery,
    GetEventsQuery,
    ListEventsQuery,
    UpdateEventCategoryCommand,
    UpdateEventCommand,
    UpdateEventsVisibilityCommand,
)
from app.core.content.events.application.errors import (
    EventCategoryNotFoundError,
    EventCategorySlugConflictError,
    EventNotFoundError,
)
from app.core.content.events.application.queries import (
    GetEvent,
    GetEvents,
    ListEventCategories,
    ListEvents,
    ListEventYears,
)
from app.core.content.events.domain.errors import (
    EventServiceError,
    SyncedEventDeleteError,
    SyncedEventFieldError,
)
from app.core.users.public import RoleName, UserDetails

router = APIRouter(prefix="/api/admin", tags=["Admin - Events"])
event_manager = require_any_role(RoleName.ADMIN, RoleName.EDITOR)


@router.get("/event-categories", response_model=list[EventCategoryRead])
def get_event_categories_endpoint(
    *,
    list_event_categories_use_case: Annotated[
        ListEventCategories, Depends(provide_list_event_categories)
    ],
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    return list_event_categories_use_case.execute()


@router.post(
    "/event-categories",
    response_model=EventCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event_category_endpoint(
    *,
    create_event_category_use_case: Annotated[
        CreateEventCategory, Depends(provide_create_event_category)
    ],
    category_data: EventCategoryCreate,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        return create_event_category_use_case.execute(
            CreateEventCategoryCommand(**category_data.model_dump())
        )
    except EventCategorySlugConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    except EventServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )


@router.patch("/event-categories/{category_id}", response_model=EventCategoryRead)
def update_event_category_endpoint(
    *,
    update_event_category_use_case: Annotated[
        UpdateEventCategory, Depends(provide_update_event_category)
    ],
    category_id: int,
    category_data: EventCategoryUpdate,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        return update_event_category_use_case.execute(
            UpdateEventCategoryCommand(
                changes=category_data.model_dump(exclude_unset=True),
                category_id=category_id,
            )
        )
    except EventCategoryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    except EventCategorySlugConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    except EventServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )


@router.get("/events", response_model=list[EventRead])
def get_events_endpoint(
    *,
    list_events_use_case: Annotated[ListEvents, Depends(provide_list_events)],
    year: Annotated[int | None, Query(ge=1900, le=2200)] = None,
    category_id: Annotated[list[int] | None, Query()] = None,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    return list_events_use_case.execute(
        ListEventsQuery(year=year, category_ids=category_id)
    )


@router.get("/event-years", response_model=list[int])
def get_event_years_endpoint(
    *,
    list_event_years_use_case: Annotated[
        ListEventYears, Depends(provide_list_event_years)
    ],
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    return list_event_years_use_case.execute()


@router.get("/events/{event_id}", response_model=EventRead)
def get_event_endpoint(
    *,
    get_event_use_case: Annotated[GetEvent, Depends(provide_get_event)],
    event_id: int,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        return get_event_use_case.execute(GetEventQuery(event_id=event_id))
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event_endpoint(
    *,
    create_event_use_case: Annotated[CreateEvent, Depends(provide_create_event)],
    get_event_use_case: Annotated[GetEvent, Depends(provide_get_event)],
    event_data: EventCreate,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        event = create_event_use_case.execute(
            CreateEventCommand(
                **event_data.model_dump(), created_by_user_id=current_user.id
            )
        )
        return get_event_use_case.execute(GetEventQuery(event_id=event.id))
    except EventServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )


@router.patch("/events/bulk/visibility", response_model=list[EventRead])
def update_events_visibility_endpoint(
    *,
    update_events_visibility_use_case: Annotated[
        UpdateEventsVisibility, Depends(provide_update_events_visibility)
    ],
    get_events_use_case: Annotated[GetEvents, Depends(provide_get_events)],
    data: EventBulkVisibilityUpdate,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        events = update_events_visibility_use_case.execute(
            UpdateEventsVisibilityCommand(
                event_ids=data.event_ids, visibility=data.visibility
            )
        )
        return get_events_use_case.execute(
            GetEventsQuery(event_ids=[event.id for event in events])
        )
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("/events/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_events_endpoint(
    *,
    delete_events_use_case: Annotated[DeleteEvents, Depends(provide_delete_events)],
    data: EventIds,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        delete_events_use_case.execute(DeleteEventsCommand(event_ids=data.event_ids))
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    except SyncedEventDeleteError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_endpoint(
    *,
    delete_event_use_case: Annotated[DeleteEvent, Depends(provide_delete_event)],
    event_id: int,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        delete_event_use_case.execute(DeleteEventCommand(event_id=event_id))
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    except SyncedEventDeleteError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.patch("/events/{event_id}", response_model=EventRead)
def update_event_endpoint(
    *,
    update_event_use_case: Annotated[UpdateEvent, Depends(provide_update_event)],
    get_event_use_case: Annotated[GetEvent, Depends(provide_get_event)],
    event_id: int,
    event_data: EventUpdate,
    current_user: Annotated[UserDetails, Depends(event_manager)],
):
    try:
        event = update_event_use_case.execute(
            UpdateEventCommand(
                changes=event_data.model_dump(exclude_unset=True), event_id=event_id
            )
        )
        return get_event_use_case.execute(GetEventQuery(event_id=event.id))
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    except SyncedEventFieldError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    except EventServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
