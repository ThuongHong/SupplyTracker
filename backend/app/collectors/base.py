from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import CollectionLog, DataCoverage

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    rows: int
    errors: list[str] = field(default_factory=list)


class BaseCollector(ABC):
    source_name: ClassVar[str]

    def run(self, session: Session) -> CollectionResult:
        log = CollectionLog(
            started_at=datetime.now(timezone.utc),
            source=self.source_name,
        )
        session.add(log)
        session.flush()

        result = CollectionResult(rows=0)
        try:
            result = self.collect(session)
            log.rows_collected = result.rows
            log.status = "success"
            if result.errors:
                log.error = "\n".join(result.errors)
        except Exception as exc:
            log.status = "error"
            log.error = str(exc)
            result.errors.append(str(exc))
        finally:
            log.finished_at = datetime.now(timezone.utc)
            session.commit()

        return result

    @abstractmethod
    def collect(self, session: Session) -> CollectionResult:
        ...

    def _retry_request(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs: object,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = client.request(method, url, **kwargs)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = base_delay * (2 ** attempt)
                    else:
                        delay = base_delay * (2 ** attempt)
                    if attempt < max_retries - 1:
                        logger.warning(
                            "Rate limited by %s, retrying in %.1fs (attempt %d/%d)",
                            url,
                            delay,
                            attempt + 1,
                            max_retries,
                        )
                        time.sleep(delay)
                        continue
                    response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                raise
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Request error for %s: %s, retrying in %.1fs",
                        url,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
        raise RuntimeError(
            f"Max retries ({max_retries}) exceeded for {url}"
        ) from last_exc

    def _upsert_coverage(
        self,
        session: Session,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        source: str,
        observed_at: datetime,
        status: str = "success",
    ) -> None:
        now = datetime.now(timezone.utc)

        stmt = (
            pg_insert(DataCoverage)
            .values(
                source=source,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                first_observed_at=observed_at,
                latest_observed_at=observed_at,
                observed_rows=1,
                expected_days=0,
                missing_days=0,
                freshness_status=_compute_freshness(observed_at, now),
                last_collection_status=status,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["source", "entity_type", "entity_id"],
                set_={
                    "entity_name": entity_name,
                    "latest_observed_at": pg_insert(DataCoverage)
                    .excluded.latest_observed_at,
                    "observed_rows": DataCoverage.observed_rows + 1,
                    "freshness_status": _compute_freshness(observed_at, now),
                    "last_collection_status": status,
                    "updated_at": now,
                },
            )
        )
        session.execute(stmt)

        existing = session.get(
            DataCoverage,
            {"source": source, "entity_type": entity_type, "entity_id": entity_id},
        )
        if existing is not None and existing.first_observed_at is not None:
            first = existing.first_observed_at
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            expected = (now - first).days
            missing = max(0, expected - existing.observed_rows)
            existing.expected_days = expected
            existing.missing_days = missing
            session.flush()


def _compute_freshness(observed_at: datetime, now: datetime) -> str:
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age_hours = (now - observed_at).total_seconds() / 3600
    if age_hours < 24:
        return "fresh"
    if age_hours < 48:
        return "stale"
    return "missing"
