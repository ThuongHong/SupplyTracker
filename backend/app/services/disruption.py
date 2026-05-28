from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DisruptionPropagation, RiskStoryEvent

# Hardcoded lane → downstream port LOCODE mapping
LANE_PORTS: dict[str, list[str]] = {
    "hormuz": ["AEFJR", "KWKWI", "IRBND"],
    "suez": ["EGPSD", "EGALY"],
    "malacca": ["SGSIN", "MYPEN"],
    "bab_el_mandeb": ["DJJIB", "YEMOK"],
    "taiwan_strait": ["TWKHH", "CNNBO"],
    "dover": ["GBFXT", "NLRTM"],
    "panama": ["PAONX", "PABLB"],
    "lombok": ["IDBPN", "IDDJB"],
}

# Chokepoint entity_id to lane mapping (adjust to match your data)
_CHOKEPOINT_LANE_MAP: dict[str, str] = {
    "hormuz": "hormuz",
    "strait_of_hormuz": "hormuz",
    "suez": "suez",
    "suez_canal": "suez",
    "malacca": "malacca",
    "strait_of_malacca": "malacca",
    "bab_el_mandeb": "bab_el_mandeb",
    "bab-el-mandeb": "bab_el_mandeb",
    "taiwan_strait": "taiwan_strait",
    "taiwan strait": "taiwan_strait",
    "dover": "dover",
    "strait_of_dover": "dover",
    "panama": "panama",
    "panama_canal": "panama",
    "lombok": "lombok",
    "lombok_strait": "lombok",
}

_HIGH_SEVERITIES = {"high", "critical"}


def propagate_chokepoint_event(
    session: Session,
    event: RiskStoryEvent,
) -> list[DisruptionPropagation]:
    """Create DisruptionPropagation rows for downstream ports affected by a chokepoint event.

    Only acts on events with severity in {"high", "critical"}.
    Returns the written rows.
    """
    if event.severity not in _HIGH_SEVERITIES:
        return []

    # Find the lane for this chokepoint
    entity_id_lower = event.entity_id.lower()
    lane = _CHOKEPOINT_LANE_MAP.get(entity_id_lower)

    if lane is None:
        # Try partial match
        for key, mapped_lane in _CHOKEPOINT_LANE_MAP.items():
            if key in entity_id_lower or entity_id_lower in key:
                lane = mapped_lane
                break

    if lane is None:
        return []

    target_ports = LANE_PORTS.get(lane, [])
    if not target_ports:
        return []

    now = datetime.now(tz=timezone.utc)
    written: list[DisruptionPropagation] = []

    for port_id in target_ports:
        row = DisruptionPropagation(
            source_entity_type=event.entity_type,
            source_entity_id=event.entity_id,
            source_entity_name=event.entity_name,
            target_entity_type="port",
            target_entity_id=port_id,
            target_entity_name=port_id,  # name not known from ID alone
            route_lane=lane,
            severity=event.severity,
            confidence=event.confidence,
            explanation=(
                f"Chokepoint {event.entity_id} event ({event.event_type}) "
                f"with severity {event.severity} may disrupt port {port_id} "
                f"via lane {lane}."
            ),
            started_at=now,
            status="active",
        )
        session.add(row)
        written.append(row)

    session.flush()
    return written
