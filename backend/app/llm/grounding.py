from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import (
    Chokepoint,
    ChokepointRiskScore,
    ChokepointStatus,
    DisruptionPropagation,
    EntityRiskForecast,
    FreightIndex,
    Port,
    PortCongestion,
    PortRiskScore,
    RiskStoryEvent,
)

logger = logging.getLogger(__name__)

_PER_ENTITY_TOKEN_CAP = 600
_TOTAL_TOKEN_CAP = 2500


def _estimate_tokens(text: str) -> int:
    """Heuristic token count: ~1.33 words per token (1 token ≈ 0.75 words)."""
    return max(1, len(text.split()) * 4 // 3)


def _truncate_to_tokens(text: str, cap: int) -> str:
    """Truncate text so its estimated token count does not exceed cap."""
    if _estimate_tokens(text) <= cap:
        return text
    # Binary-search-free approach: trim word by word from the end
    words = text.split()
    while words and (len(words) * 4 // 3) > cap:
        words = words[: int(cap * 3 / 4)]
    truncated = " ".join(words)
    return truncated + " [truncated]"


# ---------------------------------------------------------------------------
# Per-entity grounding
# ---------------------------------------------------------------------------


def build_entity_grounding(session: Session, entity: dict[str, Any]) -> str:  # noqa: C901
    """Return a compact text block (≤ _PER_ENTITY_TOKEN_CAP tokens) for one entity."""
    entity_type = entity.get("entity_type") or entity.get("type", "")
    entity_id = entity.get("entity_id") or entity.get("id", "")

    if not entity_type or not entity_id:
        return f"(skipped entity with missing type/id: {entity!r})"

    lines: list[str] = []
    now = datetime.now(UTC)
    cutoff_30d = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)

    # -----------------------------------------------------------------------
    # 1. Risk score — latest + 30d stats
    # -----------------------------------------------------------------------
    if entity_type == "port":
        RiskModel = PortRiskScore
        risk_filter = PortRiskScore.entity_id == entity_id
    else:
        RiskModel = ChokepointRiskScore
        risk_filter = ChokepointRiskScore.entity_id == entity_id

    latest_risk = (
        session.query(RiskModel)
        .filter(risk_filter)
        .order_by(desc(RiskModel.as_of))
        .first()
    )

    entity_label = entity_id
    if latest_risk:
        entity_label = latest_risk.entity_name

    if entity_type == "port":
        lines.append(f'Entity: port "{entity_label}" ({entity_id})')
    else:
        lines.append(f'Entity: chokepoint "{entity_label}" ({entity_id})')

    if latest_risk and latest_risk.score is not None:
        # 30d aggregate
        stats_30d = (
            session.query(
                func.avg(RiskModel.score),
                func.max(RiskModel.score),
            )
            .filter(risk_filter, RiskModel.as_of >= cutoff_30d)
            .one()
        )
        mean_30d = stats_30d[0]
        max_30d = stats_30d[1]

        risk_line = f"  Risk: latest={latest_risk.score:.2f}"
        if mean_30d is not None:
            risk_line += f"  30d_mean={mean_30d:.2f}"
        if max_30d is not None:
            risk_line += f"  30d_max={max_30d:.2f}"
        risk_line += f"  severity={latest_risk.severity}"
        lines.append(risk_line)
    else:
        lines.append("  Risk: no data available")

    # -----------------------------------------------------------------------
    # 2. Vessel count / dwell hours (port → PortCongestion; chokepoint → ChokepointStatus)
    # -----------------------------------------------------------------------
    if entity_type == "port":
        # Resolve Port.id from entity_id (locode or name-based)
        port_row = (
            session.query(Port)
            .filter(Port.locode == entity_id)
            .first()
        )
        if port_row is None:
            # Fall back to name match
            port_row = (
                session.query(Port)
                .filter(func.lower(Port.name) == entity_id.lower())
                .first()
            )
        if port_row:
            latest_cong = (
                session.query(PortCongestion)
                .filter(PortCongestion.port_id == port_row.id)
                .order_by(desc(PortCongestion.time))
                .first()
            )
            if latest_cong:
                # 30d aggregates for vessel count and dwell
                cong_stats = (
                    session.query(
                        func.avg(PortCongestion.total_in_area),
                        func.avg(PortCongestion.avg_dwell_hours),
                        func.max(PortCongestion.avg_dwell_hours),
                    )
                    .filter(
                        PortCongestion.port_id == port_row.id,
                        PortCongestion.time >= cutoff_30d,
                    )
                    .one()
                )
                mean_vessels = cong_stats[0]
                mean_dwell = cong_stats[1]
                max_dwell = cong_stats[2]

                vessel_line = f"  Vessel count latest: {latest_cong.total_in_area}"
                if mean_vessels is not None:
                    vessel_line += f"  (30d mean {mean_vessels:.0f})"
                lines.append(vessel_line)

                if latest_cong.avg_dwell_hours is not None:
                    dwell_line = f"  Avg dwell hours latest: {latest_cong.avg_dwell_hours:.1f}"
                    if mean_dwell is not None:
                        dwell_line += f"  (30d mean {mean_dwell:.1f}"
                        if max_dwell is not None:
                            dwell_line += f", 30d max {max_dwell:.1f}"
                        dwell_line += ")"
                    lines.append(dwell_line)

    else:
        # Chokepoint: resolve Chokepoint.id
        cp_row = (
            session.query(Chokepoint)
            .filter(func.lower(Chokepoint.name) == entity_id.lower())
            .first()
        )
        if cp_row is None:
            # Try by name exact match (entity_id may already be the name string)
            cp_row = (
                session.query(Chokepoint)
                .filter(Chokepoint.name == entity_id)
                .first()
            )
        if cp_row:
            latest_cs = (
                session.query(ChokepointStatus)
                .filter(ChokepointStatus.chokepoint_id == cp_row.id)
                .order_by(desc(ChokepointStatus.time))
                .first()
            )
            if latest_cs:
                cs_stats = (
                    session.query(func.avg(ChokepointStatus.vessel_count))
                    .filter(
                        ChokepointStatus.chokepoint_id == cp_row.id,
                        ChokepointStatus.time >= cutoff_30d,
                    )
                    .scalar()
                )
                vessel_line = f"  Vessel count latest: {latest_cs.vessel_count}"
                if cs_stats is not None:
                    vessel_line += f"  (30d mean {cs_stats:.0f})"
                lines.append(vessel_line)

    # -----------------------------------------------------------------------
    # 3. Forecast — latest EntityRiskForecast, first prediction point
    # -----------------------------------------------------------------------
    forecast_row = (
        session.query(EntityRiskForecast)
        .filter(
            EntityRiskForecast.entity_type == entity_type,
            EntityRiskForecast.entity_id == entity_id,
        )
        .order_by(desc(EntityRiskForecast.created_at))
        .first()
    )
    if forecast_row and forecast_row.predictions:
        first_pred = forecast_row.predictions[0]
        pred_score = first_pred.get("predicted_score")
        lo = first_pred.get("lower_bound")
        hi = first_pred.get("upper_bound")
        if pred_score is not None:
            fc_line = f"  Forecast (next 7d): {pred_score:.2f}"
            if lo is not None and hi is not None:
                fc_line += f" (band {lo:.2f}–{hi:.2f})"
            if forecast_row.key_drivers:
                fc_line += f"  drivers: {forecast_row.key_drivers}"
            lines.append(fc_line)

    # -----------------------------------------------------------------------
    # 4. Freight indices — FBX and WCI latest + 7d % change
    # -----------------------------------------------------------------------
    for idx_name in ("FBX", "WCI"):
        latest_idx = (
            session.query(FreightIndex)
            .filter(FreightIndex.index_name == idx_name)
            .order_by(desc(FreightIndex.time))
            .first()
        )
        if latest_idx:
            # Find the value ~7 days ago
            old_idx = (
                session.query(FreightIndex)
                .filter(
                    FreightIndex.index_name == idx_name,
                    FreightIndex.time <= cutoff_7d,
                )
                .order_by(desc(FreightIndex.time))
                .first()
            )
            idx_line = f"  {idx_name}: {latest_idx.value:.0f}"
            if old_idx and old_idx.value and old_idx.value != 0:
                pct = (latest_idx.value - old_idx.value) / old_idx.value * 100
                sign = "+" if pct >= 0 else ""
                idx_line += f" ({sign}{pct:.1f}% 7d)"
            # Append to an Indices line or start one
            # Collect both first, then emit one combined line
            lines.append(f"  Index {idx_line.strip()}")

    # -----------------------------------------------------------------------
    # 5. Bunker prices — most recent global price (any port, VLSFO preferred)
    # -----------------------------------------------------------------------
    # We include a brief global bunker note; entity_id may not match port_code
    # so we just grab the latest available
    from app.db.models import BunkerPrice  # local import to avoid circular deps at top
    bunker_row = (
        session.query(BunkerPrice)
        .order_by(desc(BunkerPrice.time))
        .first()
    )
    if bunker_row:
        lines.append(
            f"  Bunker ({bunker_row.fuel_type} @ {bunker_row.port_code}): "
            f"${bunker_row.price_usd_per_ton:.0f}/t  as_of={bunker_row.time.date()}"
        )

    # -----------------------------------------------------------------------
    # 6. Active disruptions
    # -----------------------------------------------------------------------
    if entity_type == "port":
        disrupt_q = (
            session.query(DisruptionPropagation)
            .filter(
                DisruptionPropagation.target_entity_id == entity_id,
                DisruptionPropagation.status != "resolved",
            )
        )
    else:
        disrupt_q = (
            session.query(DisruptionPropagation)
            .filter(
                DisruptionPropagation.source_entity_id == entity_id,
                DisruptionPropagation.status != "resolved",
            )
        )
    disruptions = disrupt_q.all()
    if disruptions:
        sources = list({d.source_entity_name for d in disruptions})
        lines.append(
            f"  Active disruptions: {len(disruptions)} (sources: {', '.join(sources)})"
        )

    # -----------------------------------------------------------------------
    # 7. Recent events (last 3 RiskStoryEvent)
    # -----------------------------------------------------------------------
    events = (
        session.query(RiskStoryEvent)
        .filter(
            RiskStoryEvent.entity_id == entity_id,
            RiskStoryEvent.entity_type == entity_type,
        )
        .order_by(desc(RiskStoryEvent.event_time))
        .limit(3)
        .all()
    )
    if events:
        lines.append("  Recent events:")
        for ev in events:
            lines.append(
                f"    - [{ev.severity}] {ev.event_type} at {ev.event_time.isoformat()}: "
                f"{ev.narrative}"
            )

    block = "\n".join(lines)
    return _truncate_to_tokens(block, _PER_ENTITY_TOKEN_CAP)


# ---------------------------------------------------------------------------
# Multi-entity grounding with total token cap
# ---------------------------------------------------------------------------


def build_grounding_context(session: Session, entity_context: list[dict[str, Any]]) -> str:
    """Build grounded context for all entities with total token cap."""
    blocks: list[str] = []
    total_tokens = 0

    for entity in entity_context:
        block = build_entity_grounding(session, entity)
        block_tokens = _estimate_tokens(block)
        if total_tokens + block_tokens > _TOTAL_TOKEN_CAP:
            blocks.append("(Additional entity context truncated due to token limit)")
            break
        blocks.append(block)
        total_tokens += block_tokens

    return "\n\n".join(blocks) if blocks else "No entity context data available."
