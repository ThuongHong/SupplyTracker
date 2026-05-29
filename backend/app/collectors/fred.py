from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import FreightIndex

logger = logging.getLogger(__name__)

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


class FREDCollector(BaseCollector):
    source_name = "fred"

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()
        api_key = settings.fred_api_key.get_secret_value()
        if not api_key:
            raise ValueError("FRED API key not configured")

        series_list = settings.fred_series
        total = 0
        errors: list[str] = []

        with httpx.Client(timeout=30.0) as client:
            for series_id in series_list:
                try:
                    total += self._collect_series(session, client, series_id, api_key)
                except Exception as exc:
                    err_msg = f"FRED series {series_id} failed: {exc}"
                    logger.warning(err_msg)
                    errors.append(err_msg)

        session.commit()
        return CollectionResult(rows=total, errors=errors)

    def _collect_series(
        self,
        session: Session,
        client: httpx.Client,
        series_id: str,
        api_key: str,
    ) -> int:
        resp = self._retry_request(
            client,
            "GET",
            _FRED_BASE,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 30,
            },
        )
        resp.raise_for_status()
        observations = resp.json().get("observations", [])

        count = 0
        for obs in observations:
            raw_value = obs.get("value", ".")
            if raw_value == ".":
                continue
            try:
                value = float(raw_value)
            except (ValueError, TypeError):
                continue

            obs_date = obs["date"]
            time_dt = datetime.fromisoformat(obs_date).replace(tzinfo=UTC)

            self._upsert_freight_index(
                session,
                time=time_dt,
                index_name=series_id,
                value=value,
                source="fred",
            )
            count += 1

        return count

    def _upsert_freight_index(
        self,
        session: Session,
        *,
        time: datetime,
        index_name: str,
        value: float,
        source: str,
    ) -> None:
        stmt = (
            pg_insert(FreightIndex)
            .values(
                time=time,
                index_name=index_name,
                value=value,
                source=source,
            )
            .on_conflict_do_update(
                index_elements=["time", "index_name"],
                set_={"value": value, "source": source},
            )
        )
        session.execute(stmt)
