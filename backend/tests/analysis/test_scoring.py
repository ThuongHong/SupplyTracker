from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.analysis.scoring import ComponentDef, load_components, severity_from_score


class TestSeverityFromScore:
    def test_below_first_threshold_is_low(self) -> None:
        assert severity_from_score(0.1, [0.3, 0.6, 0.8]) == "low"

    def test_between_first_and_second_is_elevated(self) -> None:
        assert severity_from_score(0.45, [0.3, 0.6, 0.8]) == "elevated"

    def test_between_second_and_third_is_high(self) -> None:
        assert severity_from_score(0.7, [0.3, 0.6, 0.8]) == "high"

    def test_at_third_threshold_is_critical(self) -> None:
        assert severity_from_score(0.8, [0.3, 0.6, 0.8]) == "critical"

    def test_above_third_threshold_is_critical(self) -> None:
        assert severity_from_score(0.82, [0.3, 0.6, 0.8]) == "critical"

    def test_exactly_first_threshold_is_elevated(self) -> None:
        assert severity_from_score(0.3, [0.3, 0.6, 0.8]) == "elevated"

    def test_zero_score_is_low(self) -> None:
        assert severity_from_score(0.0, [0.3, 0.6, 0.8]) == "low"

    def test_one_score_is_critical(self) -> None:
        assert severity_from_score(1.0, [0.3, 0.6, 0.8]) == "critical"


class TestLoadComponents:
    def test_load_components_returns_list_and_config(self) -> None:
        components, config = load_components()
        assert isinstance(components, list)
        assert len(components) > 0
        assert "severity_thresholds" in config
        assert "max_missing_fraction" in config

    def test_component_has_required_fields(self) -> None:
        components, _ = load_components()
        for comp in components:
            assert hasattr(comp, "name")
            assert hasattr(comp, "metric")
            assert hasattr(comp, "weight")
            assert hasattr(comp, "baseline_window_days")
            assert hasattr(comp, "direction")
            assert hasattr(comp, "entity_types")
            assert comp.direction in ("higher_is_better", "higher_is_worse")

    def test_port_components_present(self) -> None:
        components, _ = load_components()
        port_components = [c for c in components if "port" in c.entity_types]
        assert len(port_components) >= 3

    def test_chokepoint_components_present(self) -> None:
        components, _ = load_components()
        cp_components = [c for c in components if "chokepoint" in c.entity_types]
        assert len(cp_components) >= 2

    def test_cross_source_signals_present(self) -> None:
        components, _ = load_components()
        by_name = {c.name: c for c in components}
        assert by_name["news_pressure"].source == "news"
        assert by_name["news_pressure"].direction == "higher_is_worse"
        assert by_name["macro_stress"].source == "macro"
        assert by_name["macro_stress"].index_name == "FBX"

    def test_weights_sum_to_one_per_entity_type(self) -> None:
        components, _ = load_components()
        for et in ("port", "chokepoint"):
            total = sum(c.weight for c in components if et in c.entity_types)
            assert total == pytest.approx(1.0)


class TestScoreEntity:
    """Test score_entity using mocked session to avoid a live DB."""

    def _make_metric_row(self, value: float) -> MagicMock:
        row = MagicMock()
        row.metric_value = value
        row.observed_at = datetime(2024, 1, 15, tzinfo=timezone.utc)
        return row

    def _make_session_with_data(
        self,
        latest_value: float | None = 50.0,
        baseline_rows: list | None = None,
    ) -> MagicMock:
        """Session that returns a metric row for `.first()` and baseline rows for `.all()`."""
        session = MagicMock()
        if baseline_rows is None:
            baseline_rows = [self._make_metric_row(v) for v in [40.0, 45.0, 50.0, 55.0, 60.0]]

        if latest_value is not None:
            latest_row = self._make_metric_row(latest_value)
        else:
            latest_row = None

        # Chain for .first() calls (latest metric)
        session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            latest_row
        )
        # Chain for .all() calls (baseline computation)
        session.query.return_value.filter.return_value.all.return_value = baseline_rows
        # execute / flush are no-ops
        session.execute.return_value = MagicMock()
        session.flush.return_value = None
        return session

    def test_severity_bucketing_critical(self) -> None:
        """A very high z-score should push score into critical bucket."""
        assert severity_from_score(0.82, [0.3, 0.6, 0.8]) == "critical"

    def test_missing_component_gate_all_missing(self) -> None:
        """If all components missing → severity=unknown, score=None."""
        from app.analysis.scoring import score_entity

        session = self._make_session_with_data(latest_value=None, baseline_rows=[])
        # Session returns None for every .first() call
        session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )
        session.execute.return_value = MagicMock()
        session.flush.return_value = None

        components, _ = load_components()
        port_components = [c for c in components if "port" in c.entity_types]

        risk_score, snapshot = score_entity(
            session,
            entity_type="port",
            entity_id="SGSIN",
            entity_name="Singapore",
            as_of_date=date(2024, 1, 15),
            components=port_components,
        )
        assert snapshot.severity == "unknown"
        assert snapshot.risk_score is None

    def test_partial_coverage_produces_score(self) -> None:
        """With some components present and missing_fraction <= max_missing, score is computed."""
        from app.analysis.scoring import score_entity

        call_count = 0

        def first_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return a value for first 2 calls, None for the rest
            if call_count <= 2:
                return self._make_metric_row(50.0)
            return None

        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value.first.side_effect = (
            first_side_effect
        )
        session.query.return_value.filter.return_value.all.return_value = [
            self._make_metric_row(v) for v in [40.0, 45.0, 50.0, 55.0, 60.0]
        ]
        session.execute.return_value = MagicMock()
        session.flush.return_value = None

        components, _ = load_components()
        # Use all components for port+chokepoint (6 total), 2 present → 4/6 missing = 0.67 > 0.5
        # Use only port components (3 total), 2 present → 1/3 missing = 0.33 <= 0.5 → OK
        port_components = [c for c in components if c.entity_types == ["port"]]
        # port-only (not shared): throughput, dwell_time, congestion
        pure_port = [c for c in components if c.entity_types == ["port"]]

        if len(pure_port) >= 3:
            risk_score, snapshot = score_entity(
                session,
                entity_type="port",
                entity_id="SGSIN",
                entity_name="Singapore",
                as_of_date=date(2024, 1, 15),
                components=pure_port,
            )
            # 2 of 3 present → missing_fraction = 1/3 ≈ 0.33 <= 0.5
            assert snapshot.risk_score is not None
            assert snapshot.severity != "unknown"

    def test_z_scores_shape_in_snapshot(self) -> None:
        """z_scores in the snapshot must have {metric: {z_30d: ..., z_90d: ...}} structure."""
        from app.analysis.scoring import score_entity

        session = self._make_session_with_data(latest_value=50.0)
        components, _ = load_components()
        port_components = [c for c in components if "port" in c.entity_types]

        _, snapshot = score_entity(
            session,
            entity_type="port",
            entity_id="SGSIN",
            entity_name="Singapore",
            as_of_date=date(2024, 1, 15),
            components=port_components,
        )
        for metric, zd in snapshot.z_scores.items():
            assert "z_30d" in zd, f"z_30d missing for {metric}"
            assert "z_90d" in zd, f"z_90d missing for {metric}"
