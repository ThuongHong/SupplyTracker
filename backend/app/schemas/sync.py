from __future__ import annotations

from pydantic import BaseModel


class SyncResponse(BaseModel):
    task_id: str
    source: str


class EntitySyncResponse(BaseModel):
    entity_type: str
    entity_id: str
    rows: int
    is_tracked: bool
    errors: list[str] = []
