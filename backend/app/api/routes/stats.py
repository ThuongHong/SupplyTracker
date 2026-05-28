from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.db.models import DataCoverage
from app.schemas.stats import CoverageItem, CoverageResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])


@router.get("/stats/coverage", response_model=CoverageResponse)
def get_coverage(
    db: DbSession,
    source: str | None = Query(None, description="Filter by data source"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
) -> CoverageResponse:
    """Return DataCoverage rows, optionally filtered by source and/or entity_type."""
    q = db.query(DataCoverage)

    if source is not None:
        q = q.filter(DataCoverage.source == source)
    if entity_type is not None:
        q = q.filter(DataCoverage.entity_type == entity_type)

    rows = q.order_by(DataCoverage.source, DataCoverage.entity_type, DataCoverage.entity_id).limit(500).all()

    items = [
        CoverageItem(
            source=r.source,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            entity_name=r.entity_name,
            first_observed_at=r.first_observed_at,
            latest_observed_at=r.latest_observed_at,
            observed_rows=r.observed_rows,
            expected_days=r.expected_days,
            missing_days=r.missing_days,
            freshness_status=r.freshness_status,
            last_collection_status=r.last_collection_status,
            updated_at=r.updated_at,
            metadata=r.metadata_,
        )
        for r in rows
    ]

    return CoverageResponse(items=items, count=len(items))
