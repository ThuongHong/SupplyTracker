from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import Chokepoint, Port, PortWatchMetric

logger = logging.getLogger(__name__)


class PortWatchCollector(BaseCollector):
    source_name = "portwatch"

    def collect(self, session: Session) -> int:
        settings = get_settings()
        base_url = str(settings.portwatch_base_url).rstrip("/")

        with httpx.Client(timeout=30.0) as client:
            port_count = session.query(Port).count()
            cp_count = session.query(Chokepoint).count()
            if port_count == 0 or cp_count == 0:
                self._bootstrap(session, client, base_url)

            return self._collect_metrics(session, client, base_url)

    def _bootstrap(self, session: Session, client: httpx.Client, base_url: str) -> None:
        try:
            resp = self._retry_request(client, "GET", f"{base_url}/ports")
            resp.raise_for_status()
            ports_data = resp.json()
            self._upsert_ports(session, ports_data)
        except Exception as exc:
            logger.warning("Port bootstrap failed: %s", exc)

        try:
            resp = self._retry_request(client, "GET", f"{base_url}/chokepoints")
            resp.raise_for_status()
            cp_data = resp.json()
            self._upsert_chokepoints(session, cp_data)
        except Exception as exc:
            logger.warning("Chokepoint bootstrap failed: %s", exc)

    def _upsert_ports(self, session: Session, ports_data: list[dict]) -> None:
        for item in ports_data:
            lat = item.get("latitude", 0.0)
            lon = item.get("longitude", 0.0)
            geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
            locode = item.get("locode")
            conflict_col = "locode" if locode else "name"
            stmt = (
                pg_insert(Port)
                .values(
                    locode=locode,
                    name=item.get("name", ""),
                    country=item.get("country", ""),
                    region=item.get("region"),
                    geom=geom,
                )
                .on_conflict_do_update(
                    index_elements=[conflict_col],
                    set_={
                        "name": item.get("name", ""),
                        "country": item.get("country", ""),
                        "region": item.get("region"),
                        "geom": geom,
                    },
                )
            )
            session.execute(stmt)
        session.flush()

    def _upsert_chokepoints(self, session: Session, cp_data: list[dict]) -> None:
        for item in cp_data:
            polygon_wkt = item.get("polygon_wkt")
            if polygon_wkt:
                geom = WKTElement(polygon_wkt, srid=4326)
            else:
                lat = item.get("latitude", 0.0)
                lon = item.get("longitude", 0.0)
                geom = WKTElement(_circle_polygon_wkt(lon, lat, radius_deg=0.5), srid=4326)
            stmt = (
                pg_insert(Chokepoint)
                .values(name=item.get("name", ""), geom=geom)
                .on_conflict_do_update(
                    index_elements=["name"],
                    set_={"geom": geom},
                )
            )
            session.execute(stmt)
        session.flush()

    def _collect_metrics(
        self, session: Session, client: httpx.Client, base_url: str
    ) -> int:
        today = date.today().isoformat()
        resp = self._retry_request(
            client, "GET", f"{base_url}/metrics", params={"date": today}
        )
        resp.raise_for_status()
        rows_data: list[dict] = resp.json()

        total = 0
        errors: list[str] = []
        for item in rows_data:
            try:
                total += self._process_metric_row(session, item, today)
            except Exception as exc:
                errors.append(str(exc))
                logger.warning("Failed to process metric row %s: %s", item, exc)

        session.commit()
        return total

    def _process_metric_row(
        self, session: Session, item: dict, date_str: str
    ) -> int:
        observed_at = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        entity_type = item["entity_type"]
        entity_id = item["entity_id"]
        entity_name = item.get("entity_name", "")
        metric_name = item["metric_name"]
        value = float(item["value"])
        unit = item.get("unit")
        source_entity_id = item.get("source_entity_id")
        metadata = item.get("metadata")
        collected_at = datetime.now(timezone.utc)

        self._upsert_metric(
            session,
            observed_at=observed_at,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            metric_name=metric_name,
            metric_value=value,
            unit=unit,
            source_entity_id=source_entity_id,
            metadata_=metadata,
            collected_at=collected_at,
        )
        self._upsert_coverage(
            session, entity_type, entity_id, entity_name, "portwatch", observed_at
        )
        return 1

    def _upsert_metric(
        self,
        session: Session,
        *,
        observed_at: datetime,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        metric_name: str,
        metric_value: float,
        unit: str | None,
        source_entity_id: str | None,
        metadata_: dict | None,
        collected_at: datetime,
    ) -> None:
        stmt = (
            pg_insert(PortWatchMetric)
            .values(
                observed_at=observed_at,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                metric_name=metric_name,
                metric_value=metric_value,
                unit=unit,
                source="portwatch",
                source_entity_id=source_entity_id,
                metadata=metadata_,
                collected_at=collected_at,
            )
            .on_conflict_do_update(
                index_elements=[
                    "observed_at",
                    "entity_type",
                    "entity_id",
                    "metric_name",
                    "source",
                ],
                set_={
                    "entity_name": entity_name,
                    "metric_value": metric_value,
                    "unit": unit,
                    "source_entity_id": source_entity_id,
                    "metadata": metadata_,
                    "collected_at": collected_at,
                },
            )
        )
        session.execute(stmt)


def _circle_polygon_wkt(lon: float, lat: float, radius_deg: float = 0.5) -> str:
    points = []
    import math

    steps = 32
    for i in range(steps + 1):
        angle = 2 * math.pi * i / steps
        p_lon = lon + radius_deg * math.cos(angle)
        p_lat = lat + radius_deg * math.sin(angle)
        points.append(f"{p_lon} {p_lat}")
    coords = ", ".join(points)
    return f"POLYGON(({coords}))"
