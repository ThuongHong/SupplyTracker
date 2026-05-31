from __future__ import annotations

from pydantic import BaseModel


class BriefResponse(BaseModel):
    brief: str
    as_of: str
