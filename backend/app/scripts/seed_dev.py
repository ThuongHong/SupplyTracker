"""Dev seed script — populates the database with fixture ports/chokepoints and 90 days
of synthetic PortWatchMetric, FreightIndex, and BunkerPrice rows.

Run from the backend/ directory:
    python -m app.scripts.seed_dev
"""
from __future__ import annotations

import json
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import BunkerPrice, Chokepoint, FreightIndex, Port, PortWatchMetric
from app.db.session import _session_factory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_DAYS = 90
_SOURCE = "portwatch"

# Known seed entities → PortWatch business key (matches Alembic 0004).
_PORT_PORTID = {
    "AEJEA": "port744", "BEANR": "port57", "CNGZH": "port425",
    "CNNGB": "port824", "CNSHA": "port1188", "CNSZX": "port1189",
    "CNTAO": "port1069", "CNTXG": "port1297", "HKHKG": "port474",
    "KRPUS": "port1065", "MYPKG": "port960", "NLRTM": "port1114",
    "SGSIN": "port1201", "USLAX": "port664",
}
_CHOKEPOINT_PORTID = {
    "Suez Canal": "chokepoint1", "Panama Canal": "chokepoint2",
    "Bab-el-Mandeb": "chokepoint4", "Strait of Malacca": "chokepoint5",
    "Strait of Hormuz": "chokepoint6", "Strait of Gibraltar": "chokepoint8",
    "Strait of Dover": "chokepoint9", "Lombok Strait": "chokepoint15",
}


def _chokepoint_entity_id(name: str) -> str:
    return name.lower().replace(" ", "_")

_PORT_METRICS: list[tuple[str, float, float, str | None]] = [
    # (metric_name, base, noise_half_range, unit)
    ("port_calls",     150.0, 30.0, None),
    ("dwell_hours",     24.0,  8.0, "h"),
    ("anchored_count",  12.0,  5.0, None),
    ("median_speed",     8.0,  1.5, "kn"),
]

_CHOKEPOINT_METRICS: list[tuple[str, float, float, str | None]] = [
    ("transit_calls", 60.0,  15.0, None),
    ("vessel_count",  35.0,  10.0, None),
    ("median_speed",  12.0,   2.0, "kn"),
]

_FREIGHT_SERIES: list[tuple[str, float, float, str]] = [
    # (index_name, start_value, daily_walk_range, source)
    ("FBX",          1800.0, 50.0, "fbx"),
    ("WCI",          2200.0, 60.0, "wci"),
    ("DCOILBRENTEU",   82.0,  1.5, "fred"),
]

_BUNKER_PORT_CODES = ["SGSIN", "NLRTM", "USLAX"]
_BUNKER_FUEL_TYPES: list[tuple[str, float, float]] = [
    # (fuel_type, start_price, daily_walk_range)
    ("VLSFO", 550.0, 8.0),
    ("MGO",   700.0, 10.0),
]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _circle_polygon_wkt(lon: float, lat: float, radius_deg: float = 0.5) -> str:
    steps = 32
    points: list[str] = []
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        points.append(
            f"{lon + radius_deg * math.cos(angle)} {lat + radius_deg * math.sin(angle)}"
        )
    points.append(points[0])  # close the ring exactly
    return f"POLYGON(({', '.join(points)}))"


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------

def _date_range(days: int) -> list[datetime]:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return [today - timedelta(days=days - i) for i in range(days)]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def _seed_ports(session: Any) -> list[dict[str, Any]]:
    print("Seeding ports...")
    raw: list[dict[str, Any]] = json.loads((_FIXTURES_DIR / "ports_seed.json").read_text())

    for p in raw:
        geom = WKTElement(f"POINT({p['longitude']} {p['latitude']})", srid=4326)
        portid = _PORT_PORTID.get(p["locode"], f"seed-{p['locode']}")
        stmt = (
            pg_insert(Port)
            .values(
                portid=portid,
                locode=p["locode"],
                name=p["name"],
                country=p["country"],
                region=p.get("region"),
                geom=geom,
                is_tracked=True,
            )
            .on_conflict_do_update(
                index_elements=["locode"],
                set_=dict(
                    portid=portid,
                    name=p["name"],
                    country=p["country"],
                    region=p.get("region"),
                    geom=geom,
                    is_tracked=True,
                ),
            )
        )
        session.execute(stmt)

    session.commit()
    return raw


def _seed_chokepoints(session: Any) -> list[dict[str, Any]]:
    print("Seeding chokepoints...")
    raw: list[dict[str, Any]] = json.loads((_FIXTURES_DIR / "chokepoints_seed.json").read_text())

    for cp in raw:
        wkt = _circle_polygon_wkt(cp["longitude"], cp["latitude"])
        geom = WKTElement(wkt, srid=4326)
        cpid = _CHOKEPOINT_PORTID.get(cp["name"], f"seed-{cp['name']}")
        stmt = (
            pg_insert(Chokepoint)
            .values(chokepointid=cpid, name=cp["name"], geom=geom, is_tracked=True)
            .on_conflict_do_update(
                index_elements=["name"],
                set_=dict(chokepointid=cpid, geom=geom, is_tracked=True),
            )
        )
        session.execute(stmt)

    session.commit()
    return raw


def _seed_port_watch_metrics(
    session: Any,
    ports: list[dict[str, Any]],
    chokepoints: list[dict[str, Any]],
) -> None:
    dates = _date_range(_DAYS)
    n_entities = len(ports) + len(chokepoints)
    print(f"Seeding metrics ({_DAYS} days × {n_entities} entities)...")

    collected_at = datetime.now(UTC)
    rows: list[dict[str, Any]] = []

    # --- ports ---
    for p in ports:
        entity_id = _PORT_PORTID.get(p["locode"], f"seed-{p['locode']}")
        entity_name = p["name"]
        # precompute trend: slight downward dip in the middle third
        mid_start = _DAYS // 3
        mid_end = 2 * _DAYS // 3

        for day_idx, ts in enumerate(dates):
            trend = -15.0 if mid_start <= day_idx < mid_end else 0.0
            for metric_name, base, noise_range, unit in _PORT_METRICS:
                value = base + (random.random() * 2 - 1) * noise_range
                if metric_name == "port_calls":
                    value += trend
                value = max(0.0, value)
                rows.append(
                    dict(
                        observed_at=ts,
                        entity_type="port",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        metric_name=metric_name,
                        metric_value=round(value, 3),
                        unit=unit,
                        source=_SOURCE,
                        source_entity_id=None,
                        metadata_=None,
                        collected_at=collected_at,
                    )
                )

    # --- chokepoints ---
    for cp in chokepoints:
        entity_id = _chokepoint_entity_id(cp["name"])
        entity_name = cp["name"]
        for ts in dates:
            for metric_name, base, noise_range, unit in _CHOKEPOINT_METRICS:
                value = max(0.0, base + (random.random() * 2 - 1) * noise_range)
                rows.append(
                    dict(
                        observed_at=ts,
                        entity_type="chokepoint",
                        entity_id=entity_id,
                        entity_name=entity_name,
                        metric_name=metric_name,
                        metric_value=round(value, 3),
                        unit=unit,
                        source=_SOURCE,
                        source_entity_id=None,
                        metadata_=None,
                        collected_at=collected_at,
                    )
                )

    # Bulk insert with on_conflict_do_nothing in chunks to avoid huge statements
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        stmt = pg_insert(PortWatchMetric).values(chunk).on_conflict_do_nothing()
        session.execute(stmt)

    session.commit()


def _seed_freight_indices(session: Any) -> None:
    print("Seeding freight indices...")
    dates = _date_range(_DAYS)
    rows: list[dict[str, Any]] = []

    for index_name, start, walk_range, source in _FREIGHT_SERIES:
        value = start
        for ts in dates:
            value += (random.random() * 2 - 1) * walk_range
            value = max(0.0, value)
            rows.append(
                dict(
                    time=ts,
                    index_name=index_name,
                    value=round(value, 4),
                    source=source,
                    metadata_=None,
                )
            )

    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        stmt = pg_insert(FreightIndex).values(chunk).on_conflict_do_nothing()
        session.execute(stmt)

    session.commit()


def _seed_bunker_prices(session: Any) -> None:
    print("Seeding bunker prices...")
    dates = _date_range(_DAYS)
    rows: list[dict[str, Any]] = []

    for port_code in _BUNKER_PORT_CODES:
        for fuel_type, start, walk_range in _BUNKER_FUEL_TYPES:
            value = start
            for ts in dates:
                value += (random.random() * 2 - 1) * walk_range
                value = max(0.0, value)
                rows.append(
                    dict(
                        time=ts,
                        port_code=port_code,
                        fuel_type=fuel_type,
                        price_usd_per_ton=round(value, 2),
                    )
                )

    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        stmt = pg_insert(BunkerPrice).values(chunk).on_conflict_do_nothing()
        session.execute(stmt)

    session.commit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    random.seed(42)
    session = _session_factory()()
    try:
        ports = _seed_ports(session)
        chokepoints = _seed_chokepoints(session)
        _seed_port_watch_metrics(session, ports, chokepoints)
        _seed_freight_indices(session)
        _seed_bunker_prices(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print("Done.")


if __name__ == "__main__":
    main()
