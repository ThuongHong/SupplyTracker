from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class InsightItem(BaseModel):
    id: int
    generated_at: datetime
    category: str | None
    title: str
    narrative: str
    narrative_llm: str | None
    narrative_model: str | None
    narrative_generated_at: datetime | None
    metrics: dict[str, Any] | None
    priority: int
    event_type: str | None
    confidence: float | None
    affected_entities: list[dict[str, Any]] | None
    source_metrics: dict[str, Any] | None
    attention_level: str | None

    model_config = {"from_attributes": True}


class InsightsResponse(BaseModel):
    items: list[InsightItem]
    count: int
