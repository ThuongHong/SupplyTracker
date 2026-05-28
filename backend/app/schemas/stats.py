from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CoverageItem(BaseModel):
    source: str
    entity_type: str
    entity_id: str
    entity_name: str
    first_observed_at: datetime | None
    latest_observed_at: datetime | None
    observed_rows: int
    expected_days: int
    missing_days: int
    freshness_status: str
    last_collection_status: str | None
    updated_at: datetime
    metadata: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class CoverageResponse(BaseModel):
    items: list[CoverageItem]
    count: int
