from __future__ import annotations

from app.schemas.dashboard import (
    DashboardResponse,
    DashboardStats,
    DisruptionItem,
    EntityInfo,
    MacroCorrelation,
)
from app.services.dashboard import _entity_anomalies, _summary_context


def _series(values: list[float]) -> list[dict]:
    return [
        {"time": f"2026-05-{i + 1:02d}T00:00:00Z", "value": v}
        for i, v in enumerate(values)
    ]


def _dash() -> DashboardResponse:
    return DashboardResponse(
        entity=EntityInfo(type="port", id="SGSIN", name="Singapore"),
        window="30d",
        charts={},
        stats=DashboardStats(risk_latest=0.71, risk_30d_mean=0.6, risk_30d_max=0.82),
        disruptions=[
            DisruptionItem(
                source_entity_id="strait_of_hormuz", source_entity_name="Hormuz",
                target_entity_id="SGSIN", target_entity_name="Singapore",
                severity="high", confidence=0.8, explanation="Transit drop upstream",
                started_at="2026-05-20T00:00:00Z", status="active",
            )
        ],
        macro_sensitivity=[
            MacroCorrelation(
                macro="Brent", metric="port_calls", r=-0.58, lag_days=5, n=24,
                strength="moderate", insight="Brent leads port calls by 5d",
            )
        ],
    )


# baseline of 9 stable points, last point chosen per-metric
_BASE = [100, 102, 98, 101, 99, 100, 103, 97, 100]


class TestEntityAnomalies:
    def test_ranks_by_abs_z(self) -> None:
        series_by_metric = {
            "port_calls": _series([*_BASE, 101]),       # ~normal
            "import_volume": _series([*_BASE, 140]),    # big spike
            "export_volume": _series([*_BASE, 90]),     # mild dip
        }
        ranked = _entity_anomalies(series_by_metric)
        assert ranked[0][0] == "import_volume"  # largest |z| first
        assert ranked[0][1].anomaly_level == "high"

    def test_pct_change_carried(self) -> None:
        ranked = _entity_anomalies({"port_calls": _series([100, 110])})
        assert ranked[0][2] == 10.0


class TestSummaryContext:
    def test_headline_from_top_metric_and_notable_digest(self) -> None:
        series_by_metric = {
            "port_calls": _series([*_BASE, 101]),       # normal
            "import_volume": _series([*_BASE, 145]),    # biggest spike → headline
            "export_volume": _series([*_BASE, 135]),    # also high → in digest
        }
        anomalies = _entity_anomalies(series_by_metric)
        ctx = _summary_context(_dash(), anomalies)
        assert ctx["metric"] == "import_volume"  # not hardcoded port_calls
        assert ctx["anomaly_level"] == "high"
        # notable digest = OTHER off-baseline metrics, terse strings
        assert any("export_volume" in s for s in ctx["metric_anomalies"])
        assert "import_volume" not in " ".join(ctx["metric_anomalies"])  # headline excluded
        assert all(":" in s for s in ctx["metric_anomalies"])
        # other evidence still present
        assert ctx["macro_insights"] == ["Brent leads port calls by 5d"]
        assert ctx["disruptions"] == ["high: Transit drop upstream"]
        assert ctx["risk_latest"] == 0.71

    def test_empty_anomalies(self) -> None:
        ctx = _summary_context(_dash(), [])
        assert ctx["metric"] is None
        assert ctx["z_score"] is None
        assert ctx["metric_anomalies"] == []
