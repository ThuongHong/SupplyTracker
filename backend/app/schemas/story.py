from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StoryEventItem(BaseModel):
    event_key: str
    event_time: datetime
    entity_type: str
    entity_id: str
    entity_name: str
    event_type: str
    severity: str
    metric: str
    observed: float | None
    expected: float | None
    z_score: float | None
    percent_change: float | None
    drivers: dict[str, Any] | None
    source_metrics: dict[str, Any] | None
    narrative: str
    confidence: float
    attention_level: str
    data_sufficiency: dict[str, Any] | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class StoryResponse(BaseModel):
    items: list[StoryEventItem]
    count: int
