from __future__ import annotations

import logging
import math
from typing import Any

import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import Chokepoint, Port

logger = logging.getLogger(__name__)

# Master (metadata) layers — distinct from the Daily_* metric layers.
_PORTS_MASTER_LAYER = "PortWatch_ports_database/FeatureServer/0/query"
_CHOKEPOINTS_MASTER_LAYER = "PortWatch_chokepoints_database/FeatureServer/0/query"
_PAGE_SIZE = 1000  # ArcGIS maxRecordCount
_CHOKEPOINT_RADIUS_DEG = 0.5


def _circle_polygon_wkt(lon: float, lat: float, radius_deg: float = _CHOKEPOINT_RADIUS_DEG) -> str:
    steps = 32
    points = []
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        points.append(f"{lon + radius_deg * math.cos(angle)} {lat + radius_deg * math.sin(angle)}")
    # Close the ring with the EXACT first vertex — recomputing it via sin(2π)
    # yields a ~1e-16 drift that PostGIS rejects as a non-closed ring.
    points.append(points[0])
    return f"POLYGON(({', '.join(points)}))"


class CatalogCollector(BaseCollector):
    """Ingests PortWatch port/chokepoint *metadata only* — no time-series metrics.

    Idempotent on portid/chokepointid. Never resets is_tracked, and never
    overwrites an existing chokepoint name (the disruption lane map keys off it).
    """

    source_name = "catalog"

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()
        base_url = str(settings.portwatch_base_url).rstrip("/")

        total = 0
        errors: list[str] = []
        with httpx.Client(timeout=60.0) as client:
            try:
                total += self._ingest_ports(session, client, base_url)
            except Exception as exc:
                logger.warning("Port catalog ingest failed: %s", exc)
                errors.append(f"ports: {exc}")
            try:
                total += self._ingest_chokepoints(session, client, base_url)
            except Exception as exc:
                logger.warning("Chokepoint catalog ingest failed: %s", exc)
                errors.append(f"chokepoints: {exc}")

        session.commit()
        return CollectionResult(rows=total, errors=errors)

    # ── Paging ──────────────────────────────────────────────────────────────

    def _iter_features(
        self, client: httpx.Client, base_url: str, layer: str, out_fields: str
    ) -> list[dict[str, Any]]:
        features: list[dict[str, Any]] = []
        offset = 0
        while True:
            resp = self._retry_request(
                client,
                "GET",
                f"{base_url}/{layer}",
                params={
                    "where": "1=1",
                    "outFields": out_fields,
                    "orderByFields": "ObjectId ASC",
                    "resultOffset": offset,
                    "resultRecordCount": _PAGE_SIZE,
                    "returnGeometry": "false",
                    "f": "json",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            if "error" in payload:
                raise RuntimeError(f"ArcGIS error: {payload['error']}")
            batch = [f["attributes"] for f in payload.get("features", [])]
            features.extend(batch)
            if not payload.get("exceededTransferLimit") or not batch:
                break
            offset += len(batch)
        return features

    # ── Ports ─────────────────────────────────────────────────────────────────

    def _ingest_ports(self, session: Session, client: httpx.Client, base_url: str) -> int:
        rows = self._iter_features(
            client,
            base_url,
            _PORTS_MASTER_LAYER,
            "portid,portname,fullname,country,continent,lat,lon",
        )
        count = 0
        for r in rows:
            portid = r.get("portid")
            lat, lon = r.get("lat"), r.get("lon")
            if not portid or lat is None or lon is None:
                continue
            geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
            name = r.get("portname") or r.get("fullname") or portid
            stmt = (
                pg_insert(Port)
                .values(
                    portid=portid,
                    name=name,
                    country=r.get("country") or "",
                    region=r.get("continent"),
                    geom=geom,
                )
                .on_conflict_do_update(
                    index_elements=["portid"],
                    # Preserve locode and is_tracked; refresh descriptive fields.
                    set_={
                        "name": name,
                        "country": r.get("country") or "",
                        "region": r.get("continent"),
                        "geom": geom,
                    },
                )
            )
            session.execute(stmt)
            count += 1
        session.flush()
        return count

    # ── Chokepoints ─────────────────────────────────────────────────────────────

    def _ingest_chokepoints(
        self, session: Session, client: httpx.Client, base_url: str
    ) -> int:
        rows = self._iter_features(
            client,
            base_url,
            _CHOKEPOINTS_MASTER_LAYER,
            "portid,portname,fullname,lat,lon",
        )
        count = 0
        for r in rows:
            cpid = r.get("portid")
            lat, lon = r.get("lat"), r.get("lon")
            if not cpid or lat is None or lon is None:
                continue
            geom = WKTElement(_circle_polygon_wkt(float(lon), float(lat)), srid=4326)
            name = r.get("portname") or r.get("fullname") or cpid
            stmt = (
                pg_insert(Chokepoint)
                .values(chokepointid=cpid, name=name, geom=geom)
                .on_conflict_do_update(
                    index_elements=["chokepointid"],
                    # Preserve name (entity_id / lane-map key) and is_tracked.
                    set_={"geom": geom},
                )
            )
            session.execute(stmt)
            count += 1
        session.flush()
        return count
