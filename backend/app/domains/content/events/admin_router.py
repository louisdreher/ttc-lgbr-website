from app.auth.permissions import require_any_role
from app.core.database import get_session
from app.domains.content.events.schemas import (
    EventBulkVisibilityUpdate,
    EventCategoryCreate,
    EventCategoryRead,
    EventCategoryUpdate,
    EventCreate,
    EventIds,
    EventRead,
    EventUpdate,
)
from app.domains.content.events.service import (
    EventCategoryNotFoundError,
    EventCategorySlugConflictError,
    EventNotFoundError,
    EventServiceError,
    SyncedEventDeleteError,
    SyncedEventFieldError,
    create_event,
    create_event_category,
    delete_event,
    delete_events,
    get_event,
    list_event_categories,
    list_event_years,
    list_events,
    serialize_events,
    update_event,
    update_event_category,
    update_events_visibility,
)
from app.domains.users.model import RoleName, User
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

router = APIRouter(prefix="/api/admin", tags=["Admin - Events"])
event_manager = require_any_role(RoleName.ADMIN, RoleName.EDITOR)


@router.get("/event-categories", response_model=list[EventCategoryRead])
def get_event_categories_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    return list_event_categories(session)


@router.post(
    "/event-categories",
    response_model=EventCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event_category_endpoint(
    category_data: EventCategoryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        return create_event_category(session, category_data)
    except EventCategorySlugConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    except EventServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )


@router.patch("/event-categories/{category_id}", response_model=EventCategoryRead)
def update_event_category_endpoint(
    category_id: int,
    category_data: EventCategoryUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        return update_event_category(session, category_id, category_data)
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
    year: int | None = Query(default=None, ge=1900, le=2200),
    category_id: list[int] | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    return serialize_events(
        session, list_events(session, year=year, category_ids=category_id)
    )


@router.get("/event-years", response_model=list[int])
def get_event_years_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    return list_event_years(session)


@router.get("/events/{event_id}", response_model=EventRead)
def get_event_endpoint(
    event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        return serialize_events(session, [get_event(session, event_id)])[0]
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event_endpoint(
    event_data: EventCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        event = create_event(session, event_data, created_by_user_id=current_user.id)
        return serialize_events(session, [event])[0]
    except EventServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )


@router.patch("/events/bulk/visibility", response_model=list[EventRead])
def update_events_visibility_endpoint(
    data: EventBulkVisibilityUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        events = update_events_visibility(session, data.event_ids, data.visibility)
        return serialize_events(session, events)
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("/events/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_events_endpoint(
    data: EventIds,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        delete_events(session, data.event_ids)
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    except SyncedEventDeleteError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_endpoint(
    event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        delete_event(session, event_id)
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    except SyncedEventDeleteError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.patch("/events/{event_id}", response_model=EventRead)
def update_event_endpoint(
    event_id: int,
    event_data: EventUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(event_manager),
):
    try:
        event = update_event(session, event_id, event_data)
        return serialize_events(session, [event])[0]
    except EventNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    except SyncedEventFieldError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    except EventServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
