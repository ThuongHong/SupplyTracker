from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import Chokepoint, Port, PortWatchMetric

logger = logging.getLogger(__name__)

# ── PortWatch ArcGIS FeatureServer layers ──────────────────────────────────────
# PortWatch publishes its data through the IMF's public ArcGIS Online org. The
# old https://portwatch.imf.org/api/* paths never existed (404). These are the
# real query endpoints (no API key required).
_PORTS_DAILY_LAYER = "Daily_Ports_Data/FeatureServer/0/query"
_CHOKEPOINTS_DAILY_LAYER = "Daily_Chokepoints_Data/FeatureServer/0/query"

# Daily port metrics we extract: ArcGIS field → (metric_name, unit).
# Metric names match the existing convention (seed_dev / dashboard throughput).
# Per-category port calls feed the cargo-type "vessel mix" chart.
_PORT_METRICS = {
    "portcalls": ("port_calls", "vessels"),
    "import": ("import_volume", "tons"),
    "export": ("export_volume", "tons"),
    "portcalls_container": ("portcalls_container", "vessels"),
    "portcalls_dry_bulk": ("portcalls_dry_bulk", "vessels"),
    "portcalls_general_cargo": ("portcalls_general_cargo", "vessels"),
    "portcalls_roro": ("portcalls_roro", "vessels"),
    "portcalls_tanker": ("portcalls_tanker", "vessels"),
}
_PORT_OUT_FIELDS = "date,portid,portname," + ",".join(_PORT_METRICS)
# Daily chokepoint metrics (per-vessel-type transit counts feed the mix chart).
_CHOKEPOINT_METRICS = {
    "n_total": ("transit_calls", "vessels"),
    "capacity": ("transit_capacity", "tons"),
    "n_container": ("transit_container", "vessels"),
    "n_dry_bulk": ("transit_dry_bulk", "vessels"),
    "n_general_cargo": ("transit_general_cargo", "vessels"),
    "n_roro": ("transit_roro", "vessels"),
    "n_tanker": ("transit_tanker", "vessels"),
}
_CHOKE_OUT_FIELDS = "date,portid,portname," + ",".join(_CHOKEPOINT_METRICS)

# ArcGIS where-clause `IN (...)` can get long; chunk tracked ids per request.
_ID_CHUNK = 100
_BACKFILL_DAYS = 90


def _chokepoint_entity_id(name: str) -> str:
    """Match the convention used elsewhere (news collector, disruption lane map)."""
    return name.lower().replace(" ", "_")


def _chunks(seq: list[str], n: int) -> list[list[str]]:
    return [seq[i : i + n] for i in range(0, len(seq), n)]


class PortWatchCollector(BaseCollector):
    source_name = "portwatch"

    # ── Entry point: daily refresh of TRACKED entities (latest day) ────────────

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()
        base_url = str(settings.portwatch_base_url).rstrip("/")

        total = 0
        errors: list[str] = []
        with httpx.Client(timeout=30.0) as client:
            try:
                total += self._refresh_tracked_ports(session, client, base_url, errors)
            except Exception as exc:
                logger.warning("PortWatch port refresh failed: %s", exc)
                errors.append(f"ports: {exc}")
            try:
                total += self._refresh_tracked_chokepoints(
                    session, client, base_url, errors
                )
            except Exception as exc:
                logger.warning("PortWatch chokepoint refresh failed: %s", exc)
                errors.append(f"chokepoints: {exc}")

        session.commit()
        return CollectionResult(rows=total, errors=errors)

    def _refresh_tracked_ports(
        self, session: Session, client: httpx.Client, base_url: str, errors: list[str]
    ) -> int:
        tracked = session.query(Port).filter(Port.is_tracked.is_(True)).all()
        name_map = {p.portid: p.name for p in tracked}
        if not name_map:
            return 0
        latest = self._latest_date(client, base_url, _PORTS_DAILY_LAYER)
        if latest is None:
            return 0
        return self._fetch_ports(
            session, client, base_url, list(name_map), name_map,
            date_filter=f"date=DATE '{latest}'", errors=errors,
        )

    def _refresh_tracked_chokepoints(
        self, session: Session, client: httpx.Client, base_url: str, errors: list[str]
    ) -> int:
        tracked = session.query(Chokepoint).filter(Chokepoint.is_tracked.is_(True)).all()
        name_map = {c.chokepointid: c.name for c in tracked}
        if not name_map:
            return 0
        latest = self._latest_date(client, base_url, _CHOKEPOINTS_DAILY_LAYER)
        if latest is None:
            return 0
        return self._fetch_chokepoints(
            session, client, base_url, list(name_map), name_map,
            date_filter=f"date=DATE '{latest}'", errors=errors,
        )

    # ── Per-entity 90-day backfill (called by the per-entity sync endpoint) ─────

    def sync_port(self, session: Session, portid: str, name: str) -> CollectionResult:
        settings = get_settings()
        base_url = str(settings.portwatch_base_url).rstrip("/")
        errors: list[str] = []
        with httpx.Client(timeout=30.0) as client:
            latest = self._latest_date(client, base_url, _PORTS_DAILY_LAYER)
            if latest is None:
                return CollectionResult(rows=0, errors=["no port data available"])
            total = self._fetch_ports(
                session, client, base_url, [portid], {portid: name},
                date_filter=self._window_filter(latest), errors=errors,
            )
        session.commit()
        return CollectionResult(rows=total, errors=errors)

    def sync_chokepoint(
        self, session: Session, chokepointid: str, name: str
    ) -> CollectionResult:
        settings = get_settings()
        base_url = str(settings.portwatch_base_url).rstrip("/")
        errors: list[str] = []
        with httpx.Client(timeout=30.0) as client:
            latest = self._latest_date(client, base_url, _CHOKEPOINTS_DAILY_LAYER)
            if latest is None:
                return CollectionResult(rows=0, errors=["no chokepoint data available"])
            total = self._fetch_chokepoints(
                session, client, base_url, [chokepointid], {chokepointid: name},
                date_filter=self._window_filter(latest), errors=errors,
            )
        session.commit()
        return CollectionResult(rows=total, errors=errors)

    @staticmethod
    def _window_filter(latest: str) -> str:
        start = datetime.fromisoformat(str(latest)[:10]).date() - timedelta(
            days=_BACKFILL_DAYS
        )
        return f"date >= DATE '{start.isoformat()}'"

    # ── Shared fetch + emit ─────────────────────────────────────────────────────

    def _fetch_ports(
        self,
        session: Session,
        client: httpx.Client,
        base_url: str,
        portids: list[str],
        name_map: dict[str, str],
        *,
        date_filter: str,
        errors: list[str],
    ) -> int:
        total = 0
        for chunk in _chunks(portids, _ID_CHUNK):
            ids = ",".join(f"'{p}'" for p in chunk)
            rows = self._query(
                client, base_url, _PORTS_DAILY_LAYER,
                f"{date_filter} AND portid IN ({ids})",
                _PORT_OUT_FIELDS,
            )
            for row in rows:
                portid = str(row.get("portid") or "")
                if portid not in name_map:
                    continue
                total += self._emit_metrics(
                    session,
                    entity_type="port",
                    entity_id=portid,
                    entity_name=row.get("portname") or name_map[portid],
                    source_entity_id=portid,
                    observed_at=self._row_date(row),
                    row=row,
                    metric_map=_PORT_METRICS,
                    errors=errors,
                )
        return total

    def _fetch_chokepoints(
        self,
        session: Session,
        client: httpx.Client,
        base_url: str,
        ids_list: list[str],
        name_map: dict[str, str],
        *,
        date_filter: str,
        errors: list[str],
    ) -> int:
        total = 0
        for chunk in _chunks(ids_list, _ID_CHUNK):
            ids = ",".join(f"'{p}'" for p in chunk)
            rows = self._query(
                client, base_url, _CHOKEPOINTS_DAILY_LAYER,
                f"{date_filter} AND portid IN ({ids})",
                _CHOKE_OUT_FIELDS,
            )
            for row in rows:
                cpid = str(row.get("portid") or "")
                name = name_map.get(cpid)
                if name is None:
                    continue
                total += self._emit_metrics(
                    session,
                    entity_type="chokepoint",
                    entity_id=_chokepoint_entity_id(name),
                    entity_name=name,
                    source_entity_id=cpid,
                    observed_at=self._row_date(row),
                    row=row,
                    metric_map=_CHOKEPOINT_METRICS,
                    errors=errors,
                )
        return total

    @staticmethod
    def _row_date(row: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(str(row["date"])[:10]).replace(tzinfo=UTC)

    # ── ArcGIS query helpers ────────────────────────────────────────────────────

    def _query(
        self, client: httpx.Client, base_url: str, layer: str, where: str, out_fields: str
    ) -> list[dict[str, Any]]:
        resp = self._retry_request(
            client,
            "GET",
            f"{base_url}/{layer}",
            params={
                "where": where,
                "outFields": out_fields,
                "returnGeometry": "false",
                "resultRecordCount": 2000,
                "f": "json",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            raise RuntimeError(f"ArcGIS error: {payload['error']}")
        return [f["attributes"] for f in payload.get("features", [])]

    def _latest_date(
        self, client: httpx.Client, base_url: str, layer: str
    ) -> str | None:
        """Return the max ``date`` value (ISO string) in a daily layer."""
        resp = self._retry_request(
            client,
            "GET",
            f"{base_url}/{layer}",
            params={
                "where": "1=1",
                "outStatistics": (
                    '[{"statisticType":"max","onStatisticField":"date",'
                    '"outStatisticFieldName":"maxd"}]'
                ),
                "f": "json",
            },
        )
        resp.raise_for_status()
        feats = resp.json().get("features", [])
        if not feats:
            return None
        maxd = feats[0]["attributes"].get("maxd")
        return str(maxd) if maxd is not None else None

    # ── Shared upsert ─────────────────────────────────────────────────────────

    def _emit_metrics(
        self,
        session: Session,
        *,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        source_entity_id: str | None,
        observed_at: datetime,
        row: dict[str, Any],
        metric_map: dict[str, tuple[str, str]],
        errors: list[str],
    ) -> int:
        collected_at = datetime.now(UTC)
        count = 0
        for field_name, (metric_name, unit) in metric_map.items():
            raw = row.get(field_name)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (ValueError, TypeError):
                continue
            try:
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
                    collected_at=collected_at,
                )
                count += 1
            except Exception as exc:
                errors.append(f"{entity_id}/{metric_name}: {exc}")
                logger.warning("Upsert failed for %s/%s: %s", entity_id, metric_name, exc)
        if count:
            self._upsert_coverage(
                session, entity_type, entity_id, entity_name, "portwatch", observed_at
            )
        return count

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
                    "collected_at": collected_at,
                },
            )
        )
        session.execute(stmt)
