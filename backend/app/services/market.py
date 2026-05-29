"""Growth & Market Insights aggregation.

Everything here is grounded in data the app actually has:
  - trade growth: import/export volume + port calls summed across TRACKED ports
  - market: freight indices (FBX/WCI/FRED) + bunker prices
  - narrative: optional LLM summary of the above (data-driven fallback if the
    LLM is unavailable)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Port, PortWatchMetric
from app.services.dashboard import _build_bunker_chart, _build_indices_chart

logger = logging.getLogger(__name__)

_WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90}
_TRADE_METRICS = ["port_calls", "import_volume", "export_volume"]


def _pct_change(series: list[dict[str, Any]]) -> float | None:
    if len(series) < 2:
        return None
    first = float(series[0]["value"])
    last = float(series[-1]["value"])
    if not first:
        return None
    return round((last - first) / first * 100, 1)


def _aggregate_trade(
    session: Session, portids: list[str], since: datetime
) -> dict[str, Any]:
    """Sum each trade metric per day across the tracked ports."""
    result: dict[str, Any] = {}
    if not portids:
        return {m: {"latest": None, "pct_change": None, "series": []} for m in _TRADE_METRICS}

    for metric in _TRADE_METRICS:
        rows = (
            session.query(
                PortWatchMetric.observed_at,
                func.sum(PortWatchMetric.metric_value).label("total"),
            )
            .filter(
                PortWatchMetric.entity_type == "port",
                PortWatchMetric.entity_id.in_(portids),
                PortWatchMetric.metric_name == metric,
                PortWatchMetric.observed_at >= since,
            )
            .group_by(PortWatchMetric.observed_at)
            .order_by(PortWatchMetric.observed_at)
            .all()
        )
        series = [
            {"time": r.observed_at.isoformat(), "value": float(r.total)} for r in rows
        ]
        result[metric] = {
            "latest": series[-1]["value"] if series else None,
            "pct_change": _pct_change(series),
            "series": series,
        }
    return result


def _narrative(
    window: str, trade: dict[str, Any], tracked_count: int
) -> str:
    """LLM summary of the growth/market picture, with a data-driven fallback."""
    def _fallback() -> str:
        parts = [f"Across {tracked_count} tracked ports over the last {window}:"]
        labels = {
            "port_calls": "port calls",
            "import_volume": "import volume",
            "export_volume": "export volume",
        }
        for metric, label in labels.items():
            pct = trade.get(metric, {}).get("pct_change")
            if pct is not None:
                direction = "up" if pct >= 0 else "down"
                parts.append(f"{label} {direction} {abs(pct):.1f}%")
        return "; ".join(parts) + "." if len(parts) > 1 else (
            "No tracked-port trade data yet — sync some ports to populate insights."
        )

    try:
        from app.llm.client import LLMResponse, chat_completion

        summary_data = {
            m: trade.get(m, {}).get("pct_change") for m in _TRADE_METRICS
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a maritime trade analyst. In 2-3 sentences, summarize "
                    "the growth and market picture from the given percentage changes. "
                    "Be factual and concise; do not invent numbers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Window: {window}. Tracked ports: {tracked_count}. "
                    f"Percent changes (sum across tracked ports): {summary_data}."
                ),
            },
        ]
        resp = chat_completion(messages)
        if isinstance(resp, LLMResponse) and resp.content.strip():
            return resp.content.strip()
    except Exception:
        logger.info("Market narrative LLM unavailable; using data-driven fallback.")
    return _fallback()


def build_market_insights(session: Session, window: str = "30d") -> dict[str, Any]:
    days = _WINDOW_DAYS.get(window, 30)
    since = datetime.now(tz=UTC) - timedelta(days=days)

    tracked = session.query(Port).filter(Port.is_tracked.is_(True)).all()
    portids = [p.portid for p in tracked]

    trade = _aggregate_trade(session, portids, since)
    indices = _build_indices_chart(session, since)
    bunker = _build_bunker_chart(session, since)

    as_of = (
        session.query(func.max(PortWatchMetric.observed_at))
        .filter(PortWatchMetric.entity_type == "port")
        .scalar()
    )

    return {
        "window": window,
        "as_of": as_of.isoformat() if as_of else None,
        "tracked_count": len(portids),
        "trade_growth": trade,
        "market": {"indices": indices, "bunker": bunker},
        "narrative": _narrative(window, trade, len(portids)),
    }
