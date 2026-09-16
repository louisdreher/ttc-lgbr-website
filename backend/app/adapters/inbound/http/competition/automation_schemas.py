from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SyncSettingsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = True
    nightly_hour: int = Field(default=3, ge=0, le=23)
    nightly_minute: int = Field(default=0, ge=0, le=59)
    result_delay_minutes: int = Field(default=180, ge=0, le=1440)
    result_retry_minutes: int = Field(default=30, ge=5, le=1440)
    result_retry_window_hours: int = Field(default=24, ge=1, le=168)
    include_tables: bool = True
    include_registrations: bool = True


class SyncRunSchema(BaseModel):
    kind: Literal["nightly", "manual", "match"]
    started_at: datetime
    match_id: int | None
    finished_at: datetime | None
    status: Literal["running", "succeeded", "partial", "failed", "waiting"]
    imported: int
    skipped: int
    errors: list[str]


class SyncStateSchema(BaseModel):
    requested: bool
    last_nightly_slot: datetime | None
    last_nightly_success_at: datetime | None
    last_run: SyncRunSchema | None
    nightly_run: SyncRunSchema | None
    last_error: str | None
    last_error_at: datetime | None


class SyncStatusSchema(BaseModel):
    settings: SyncSettingsSchema
    state: SyncStateSchema
    heartbeat_at: datetime | None
    worker_online: bool
    running: bool
    stale_run: bool
    next_nightly_at: datetime | None
    next_match_at: datetime | None


class SyncRequestedSchema(BaseModel):
    requested: bool = True


class OutboxStatusSchema(BaseModel):
    event_id: UUID
    event_type: str
    deduplication_key: str
    occurred_at: datetime
    processed_at: datetime | None
    attempts: int
    last_error: str | None
    next_attempt_at: datetime | None
    locked_until: datetime | None
    failed_at: datetime | None
