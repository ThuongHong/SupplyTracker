from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import BunkerPrice

logger = logging.getLogger(__name__)

_BUNKER_URL_TEMPLATE = "https://www.bunkerindex.com/prices/{port_code}/{fuel_type}.json"


class BunkerCollector(BaseCollector):
    source_name = "bunker"

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()
        ports = settings.bunker_ports
        fuel_types = settings.bunker_fuel_types

        if not ports:
            logger.warning("No bunker ports configured; skipping collection")
            return CollectionResult(rows=0)

        total = 0
        errors: list[str] = []
        with httpx.Client(timeout=30.0) as client:
            for port_code in ports:
                for fuel_type in fuel_types:
                    try:
                        total += self._fetch_pair(session, client, port_code, fuel_type)
                    except Exception as exc:
                        err_msg = f"Bunker fetch failed for {port_code}/{fuel_type}: {exc}"
                        logger.warning(err_msg)
                        errors.append(err_msg)

        session.commit()
        return CollectionResult(rows=total, errors=errors)

    def _fetch_pair(
        self,
        session: Session,
        client: httpx.Client,
        port_code: str,
        fuel_type: str,
    ) -> int:
        # TODO: update HTML parsing logic once target URL format is confirmed
        url = _BUNKER_URL_TEMPLATE.format(port_code=port_code, fuel_type=fuel_type)
        resp = self._retry_request(client, "GET", url)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            rows = data.get("data", [data])
        elif isinstance(data, list):
            rows = data
        else:
            rows = []

        count = 0
        for row in rows:
            try:
                date_str = row.get("date", "")
                price = float(row.get("price", row.get("value", 0.0)))
                if not date_str:
                    continue
                time_dt = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
                self._upsert_bunker_price(
                    session,
                    time=time_dt,
                    port_code=port_code,
                    fuel_type=fuel_type,
                    price=price,
                )
                count += 1
            except Exception as exc:
                logger.warning(
                    "Bunker row parse error (%s/%s): %s — %s",
                    port_code,
                    fuel_type,
                    row,
                    exc,
                )

        return count

    def _upsert_bunker_price(
        self,
        session: Session,
        *,
        time: datetime,
        port_code: str,
        fuel_type: str,
        price: float,
    ) -> None:
        stmt = (
            pg_insert(BunkerPrice)
            .values(
                time=time,
                port_code=port_code,
                fuel_type=fuel_type,
                price_usd_per_ton=price,
            )
            .on_conflict_do_update(
                index_elements=["time", "port_code", "fuel_type"],
                set_={"price_usd_per_ton": price},
            )
        )
        session.execute(stmt)
