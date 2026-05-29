from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.db.models import PortWatchMetric

logger = logging.getLogger(__name__)

# ── PortWatch ArcGIS FeatureServer layers ──────────────────────────────────────
# PortWatch publishes its data through the IMF's public ArcGIS Online org. The
# old https://portwatch.imf.org/api/* paths never existed (404). These are the
# real query endpoints (no API key required).
_PORTS_DAILY_LAYER = "Daily_Ports_Data/FeatureServer/0/query"
_CHOKEPOINTS_DAILY_LAYER = "Daily_Chokepoints_Data/FeatureServer/0/query"

# ── Entity → PortWatch portid maps ─────────────────────────────────────────────
# Daily data is keyed by PortWatch's internal ``portid`` (e.g. "port1188"), which
# does NOT line up with UN/LOCODEs (PortWatch uses spaced, sometimes divergent
# codes — our "CNSHA" is their "CN SGH"). We therefore curate an explicit map for
# the ports/chokepoints we track. portids are stable identifiers in PortWatch.
# Resolved by name against PortWatch_ports_database, picking the busiest match.
_PORT_PORTID: dict[str, str] = {
    "AEJEA": "port744",   # Jebel Ali
    "BEANR": "port57",    # Antwerp
    "CNGZH": "port425",   # Guangzhou (Nansha)
    "CNNGB": "port824",   # Ningbo
    "CNSHA": "port1188",  # Shanghai (Pudong)
    "CNSZX": "port1189",  # Shekou (Shenzhen)
    "CNTAO": "port1069",  # Qingdao
    "CNTXG": "port1297",  # Tianjin Xin Gang
    "HKHKG": "port474",   # Hong Kong
    "KRPUS": "port1065",  # Busan
    "MYPKG": "port960",   # Port Klang
    "NLRTM": "port1114",  # Rotterdam
    "SGSIN": "port1201",  # Singapore
    "USLAX": "port664",   # Los Angeles-Long Beach
}

# Keys must match the ``name`` column in our chokepoints table exactly.
_CHOKEPOINT_PORTID: dict[str, str] = {
    "Suez Canal": "chokepoint1",
    "Panama Canal": "chokepoint2",
    "Bab-el-Mandeb": "chokepoint4",
    "Strait of Malacca": "chokepoint5",
    "Strait of Hormuz": "chokepoint6",
    "Strait of Gibraltar": "chokepoint8",
    "Strait of Dover": "chokepoint9",
    "Lombok Strait": "chokepoint15",
}

# Daily port metrics we extract: ArcGIS field → (metric_name, unit).
# Metric names match the existing convention (seed_dev / dashboard throughput).
_PORT_METRICS = {
    "portcalls": ("port_calls", "vessels"),
    "import": ("import_volume", "tons"),
    "export": ("export_volume", "tons"),
}
# Daily chokepoint metrics.
_CHOKEPOINT_METRICS = {
    "n_total": ("transit_calls", "vessels"),
    "capacity": ("transit_capacity", "tons"),
}


def _chokepoint_entity_id(name: str) -> str:
    """Match the convention used elsewhere (news collector, disruption lane map)."""
    return name.lower().replace(" ", "_")


class PortWatchCollector(BaseCollector):
    source_name = "portwatch"

    def collect(self, session: Session) -> CollectionResult:
        settings = get_settings()
        base_url = str(settings.portwatch_base_url).rstrip("/")

        total = 0
        errors: list[str] = []
        with httpx.Client(timeout=30.0) as client:
            try:
                rows, errs = self._collect_ports(session, client, base_url)
                total += rows
                errors.extend(errs)
            except Exception as exc:
                logger.warning("PortWatch port metrics failed: %s", exc)
                errors.append(f"ports: {exc}")

            try:
                rows, errs = self._collect_chokepoints(session, client, base_url)
                total += rows
                errors.extend(errs)
            except Exception as exc:
                logger.warning("PortWatch chokepoint metrics failed: %s", exc)
                errors.append(f"chokepoints: {exc}")

        session.commit()
        return CollectionResult(rows=total, errors=errors)

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

    # ── Ports ─────────────────────────────────────────────────────────────────

    def _collect_ports(
        self, session: Session, client: httpx.Client, base_url: str
    ) -> tuple[int, list[str]]:
        latest = self._latest_date(client, base_url, _PORTS_DAILY_LAYER)
        if latest is None:
            return 0, ["ports: no data available"]

        portid_to_locode = {pid: loc for loc, pid in _PORT_PORTID.items()}
        ids = ",".join(f"'{pid}'" for pid in _PORT_PORTID.values())
        where = f"date=DATE '{latest}' AND portid IN ({ids})"
        rows = self._query(
            client,
            base_url,
            _PORTS_DAILY_LAYER,
            where,
            "date,portid,portname,portcalls,import,export",
        )

        observed_at = datetime.fromisoformat(str(latest)[:10]).replace(tzinfo=UTC)
        total = 0
        errors: list[str] = []
        for row in rows:
            portid = str(row.get("portid") or "")
            locode = portid_to_locode.get(portid)
            if locode is None:
                continue
            name = row.get("portname", "") or locode
            total += self._emit_metrics(
                session,
                entity_type="port",
                entity_id=locode,
                entity_name=name,
                source_entity_id=portid,
                observed_at=observed_at,
                row=row,
                metric_map=_PORT_METRICS,
                errors=errors,
            )
        return total, errors

    # ── Chokepoints ─────────────────────────────────────────────────────────────

    def _collect_chokepoints(
        self, session: Session, client: httpx.Client, base_url: str
    ) -> tuple[int, list[str]]:
        latest = self._latest_date(client, base_url, _CHOKEPOINTS_DAILY_LAYER)
        if latest is None:
            return 0, ["chokepoints: no data available"]

        portid_to_name = {pid: name for name, pid in _CHOKEPOINT_PORTID.items()}
        ids = ",".join(f"'{pid}'" for pid in _CHOKEPOINT_PORTID.values())
        where = f"date=DATE '{latest}' AND portid IN ({ids})"
        rows = self._query(
            client,
            base_url,
            _CHOKEPOINTS_DAILY_LAYER,
            where,
            "date,portid,portname,n_total,capacity",
        )

        observed_at = datetime.fromisoformat(str(latest)[:10]).replace(tzinfo=UTC)
        total = 0
        errors: list[str] = []
        for row in rows:
            portid = str(row.get("portid") or "")
            name = portid_to_name.get(portid)
            if name is None:
                continue
            total += self._emit_metrics(
                session,
                entity_type="chokepoint",
                entity_id=_chokepoint_entity_id(name),
                entity_name=name,
                source_entity_id=portid,
                observed_at=observed_at,
                row=row,
                metric_map=_CHOKEPOINT_METRICS,
                errors=errors,
            )
        return total, errors

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
