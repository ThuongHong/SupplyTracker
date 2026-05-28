from __future__ import annotations

from pydantic import BaseModel


class SyncResponse(BaseModel):
    task_id: str
    source: str
