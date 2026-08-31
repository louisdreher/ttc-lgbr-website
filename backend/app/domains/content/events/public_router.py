from datetime import datetime

from app.core.database import get_session
from app.domains.content.events.schemas import PublicEventCategoryRead, PublicEventRead
from app.domains.content.events.service import (
    list_public_event_categories,
    list_public_events,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

router = APIRouter(prefix="/api", tags=["Public events"])


@router.get("/event-categories", response_model=list[PublicEventCategoryRead])
def get_public_event_categories(
    session: Session = Depends(get_session),
) -> list[PublicEventCategoryRead]:
    return list_public_event_categories(session)


@router.get("/events", response_model=list[PublicEventRead])
def get_public_events(
    starts_from: datetime,
    starts_until: datetime,
    category_id: list[int] | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[PublicEventRead]:
    if starts_until < starts_from:
        raise HTTPException(
            status_code=422,
            detail="Das Enddatum darf nicht vor dem Startdatum liegen.",
        )
    return list_public_events(
        session,
        starts_from=starts_from,
        starts_until=starts_until,
        category_ids=category_id,
    )
