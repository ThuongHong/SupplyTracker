from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import FreightIndex

logger = logging.getLogger(__name__)


class WCICollector(BaseCollector):
    source_name = "wci"

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()
        source_url = settings.wci_source_url
        if not source_url:
            logger.warning("WCI source URL is not configured; skipping collection")
            return CollectionResult(rows=0)

        with httpx.Client(timeout=30.0) as client:
            resp = self._retry_request(client, "GET", source_url)
            resp.raise_for_status()
            count = self._parse_and_upsert(session, resp)

        session.commit()
        return CollectionResult(rows=count)

    def _parse_and_upsert(self, session: Session, resp: httpx.Response) -> int:
        # TODO: update HTML parsing logic once target URL format is confirmed
        content_type = resp.headers.get("content-type", "")
        rows: list[dict] = []

        if "json" in content_type:
            data = resp.json()
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = data.get("data", [data])
        else:
            try:
                reader = csv.DictReader(io.StringIO(resp.text))
                rows = list(reader)
            except Exception:
                rows = []

        count = 0
        for row in rows:
            try:
                date_str = row.get("date", "")
                value_str = row.get("value", "")
                if not date_str or not value_str:
                    continue
                time_dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                value = float(value_str)
                self._upsert_freight_index(session, time=time_dt, value=value)
                count += 1
            except Exception as exc:
                logger.warning("WCI row parse error: %s — %s", row, exc)

        return count

    def _upsert_freight_index(
        self,
        session: Session,
        *,
        time: datetime,
        value: float,
    ) -> None:
        stmt = (
            pg_insert(FreightIndex)
            .values(
                time=time,
                index_name="WCI",
                value=value,
                source="wci",
                metadata=None,
            )
            .on_conflict_do_update(
                index_elements=["time", "index_name"],
                set_={"value": value, "source": "wci"},
            )
        )
        session.execute(stmt)
