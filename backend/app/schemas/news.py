from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsItemSchema(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    url: str
    title: str
    source: str
    published_at: datetime
    summary: str | None
    language: str
    fetched_at: datetime

    model_config = {"from_attributes": True}


class NewsListResponse(BaseModel):
    items: list[NewsItemSchema]
    count: int
