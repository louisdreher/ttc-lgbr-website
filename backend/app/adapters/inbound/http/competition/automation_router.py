from typing import Annotated
from uuid import UUID

from app.adapters.inbound.http.auth.permissions import require_role
from app.adapters.inbound.http.competition.automation_dependencies import (
    provide_match_reload,
    provide_outbox_retry,
    provide_outbox_status,
    provide_sync_matches,
    provide_sync_request,
    provide_sync_settings,
    provide_sync_status,
)
from app.adapters.inbound.http.competition.automation_schemas import (
    MatchReloadStatusSchema,
    OutboxStatusSchema,
    SyncMatchOverviewSchema,
    SyncRequestedSchema,
    SyncSettingsSchema,
    SyncStatusSchema,
)
from app.core.competition.application.sync.automation.commands import (
    RequestMatchReload,
    RequestSync,
    UpdateSyncSettings,
)
from app.core.competition.application.sync.automation.dto import (
    RequestMatchReloadCommand,
    UpdateSyncSettingsCommand,
)
from app.core.competition.application.sync.automation.errors import (
    MatchReloadConflictError,
    ReloadMatchNotFoundError,
)
from app.core.competition.application.sync.automation.queries import (
    GetSyncMatches,
    GetSyncStatus,
)
from app.core.competition.domain.sync_automation import SyncSettings
from app.core.messaging.application.commands import RetryOutboxMessage
from app.core.messaging.application.dto import (
    GetOutboxStatusQuery,
    RetryOutboxMessageCommand,
)
from app.core.messaging.application.queries import GetOutboxStatus
from app.core.users.public import RoleName
from fastapi import APIRouter, Depends, HTTPException, Path, Query

router = APIRouter(
    prefix="/api/admin/mytt",
    tags=["MyTischtennis administration"],
    dependencies=[Depends(require_role(RoleName.ADMIN))],
)


@router.get("/matches", response_model=SyncMatchOverviewSchema)
def get_matches(use_case: Annotated[GetSyncMatches, Depends(provide_sync_matches)]):
    return use_case.execute()


@router.post(
    "/matches/{match_id}/reload",
    status_code=202,
    response_model=MatchReloadStatusSchema,
)
def request_match_reload(
    match_id: Annotated[int, Path(gt=0)],
    use_case: Annotated[RequestMatchReload, Depends(provide_match_reload)],
):
    try:
        return use_case.execute(RequestMatchReloadCommand(match_id))
    except ReloadMatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except MatchReloadConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/status", response_model=SyncStatusSchema)
def get_status(use_case: Annotated[GetSyncStatus, Depends(provide_sync_status)]):
    return use_case.execute()


@router.get("/settings", response_model=SyncSettingsSchema)
def get_settings(use_case: Annotated[GetSyncStatus, Depends(provide_sync_status)]):
    return use_case.execute().settings


@router.put("/settings", response_model=SyncSettingsSchema)
def put_settings(
    data: SyncSettingsSchema,
    use_case: Annotated[UpdateSyncSettings, Depends(provide_sync_settings)],
):
    return use_case.execute(
        UpdateSyncSettingsCommand(SyncSettings(**data.model_dump()))
    )


@router.post("/sync", status_code=202, response_model=SyncRequestedSchema)
def request_sync(use_case: Annotated[RequestSync, Depends(provide_sync_request)]):
    use_case.execute()
    return SyncRequestedSchema()


@router.get("/outbox", response_model=list[OutboxStatusSchema])
def get_outbox(
    use_case: Annotated[GetOutboxStatus, Depends(provide_outbox_status)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 20,
):
    return use_case.execute(GetOutboxStatusQuery(limit))


@router.post("/outbox/{event_id}/retry", status_code=204)
def retry_outbox(
    event_id: UUID,
    use_case: Annotated[RetryOutboxMessage, Depends(provide_outbox_retry)],
):
    try:
        use_case.execute(RetryOutboxMessageCommand(event_id))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
