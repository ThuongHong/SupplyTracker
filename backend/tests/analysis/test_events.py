from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from app.analysis.events import detect_events
from app.analysis.scoring import is_adverse_deviation
from app.db.models import RiskFeatureSnapshot, RiskStoryEvent


class TestIsAdverseDeviation:
    def test_higher_is_better_drop_is_adverse(self) -> None:
        assert is_adverse_deviation("port_calls", -3.0) is True
        assert is_adverse_deviation("transit_calls", -2.5) is True

    def test_higher_is_better_surge_is_favorable(self) -> None:
        assert is_adverse_deviation("port_calls", 28.0) is False
        assert is_adverse_deviation("import_volume", 5.0) is False

    def test_higher_is_worse_flips(self) -> None:
        # freight_index / news rising is adverse
        assert is_adverse_deviation("freight_index", 3.0) is True
        assert is_adverse_deviation("freight_index", -3.0) is False

    def test_unknown_metric_is_adverse(self) -> None:
        assert is_adverse_deviation("mystery", 5.0) is True


def _make_snapshot(
    z_scores: dict | None = None,
    severity: str = "elevated",
    risk_score: float | None = 0.55,
    entity_type: str = "port",
    entity_id: str = "SGSIN",
    entity_name: str = "Singapore",
    feature_values: dict | None = None,
    baseline_values: dict | None = None,
    snap_date: date | None = None,
) -> RiskFeatureSnapshot:
    snap = RiskFeatureSnapshot(
        snapshot_date=snap_date or date(2024, 1, 15),
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        risk_score=risk_score,
        severity=severity,
        feature_values=feature_values or {},
        baseline_values=baseline_values or {},
        z_scores=z_scores or {},
        deltas={},
        missing_features=[],
        feature_schema_version="1.0",
    )
    return snap


def _make_session(streak_rows: list | None = None) -> MagicMock:
    """Mock session; .execute() is captured, .flush() is no-op.
    streak_rows are returned from the .all() call used in streak detection.
    """
    session = MagicMock()
    # For streak detection query
    query_mock = session.query.return_value.filter.return_value
    query_mock.order_by.return_value.all.return_value = streak_rows or []
    session.execute.return_value = MagicMock()
    session.flush.return_value = None
    return session


class TestZSpikeDetection:
    def test_favorable_surge_is_low_severity(self) -> None:
        """A surge in a higher_is_better metric (port_calls up) is favorable,
        so the z_spike event is emitted but at low severity/attention."""
        z_scores = {"port_calls": {"z_30d": 3.0, "z_90d": 2.8}}
        feature_values = {"port_calls": 120.0}
        baseline_values = {"port_calls": {"mean_30d": 80.0, "stdev_30d": 10.0}}
        snap = _make_snapshot(
            z_scores=z_scores,
            feature_values=feature_values,
            baseline_values=baseline_values,
        )
        session = _make_session()

        events = detect_events(session, snap, prev_severity=None)

        spike_events = [e for e in events if e.event_type == "z_spike"]
        assert len(spike_events) == 1
        assert spike_events[0].metric == "port_calls"
        assert spike_events[0].z_score == pytest.approx(3.0)
        assert spike_events[0].severity == "low"
        assert spike_events[0].attention_level == "low"
        assert "favorable" in spike_events[0].narrative.lower()

    def test_adverse_drop_is_high_severity(self) -> None:
        """A drop in a higher_is_better metric (port_calls down) is adverse,
        so the z_spike event keeps high severity/attention."""
        z_scores = {"port_calls": {"z_30d": -3.0, "z_90d": -2.8}}
        feature_values = {"port_calls": 40.0}
        baseline_values = {"port_calls": {"mean_30d": 80.0, "stdev_30d": 10.0}}
        snap = _make_snapshot(
            z_scores=z_scores,
            feature_values=feature_values,
            baseline_values=baseline_values,
        )
        session = _make_session()

        events = detect_events(session, snap, prev_severity=None)

        spike_events = [e for e in events if e.event_type == "z_spike"]
        assert len(spike_events) == 1
        assert spike_events[0].severity == "high"
        assert spike_events[0].confidence == pytest.approx(0.9)
        assert spike_events[0].attention_level == "high"
        assert "fell" in spike_events[0].narrative.lower()

    def test_no_z_spike_when_z_below_25(self) -> None:
        z_scores = {"port_calls": {"z_30d": 2.0, "z_90d": 1.5}}
        snap = _make_snapshot(z_scores=z_scores)
        session = _make_session()

        events = detect_events(session, snap, prev_severity=None)
        spike_events = [e for e in events if e.event_type == "z_spike"]
        assert len(spike_events) == 0

    def test_z_spike_on_negative_z(self) -> None:
        """Negative z with |z| >= 2.5 also triggers z_spike."""
        z_scores = {"dwell_hours": {"z_30d": -2.7, "z_90d": -2.0}}
        feature_values = {"dwell_hours": 5.0}
        baseline_values = {"dwell_hours": {"mean_30d": 20.0, "stdev_30d": 5.0}}
        snap = _make_snapshot(
            z_scores=z_scores,
            feature_values=feature_values,
            baseline_values=baseline_values,
        )
        session = _make_session()

        events = detect_events(session, snap, prev_severity=None)
        spike_events = [e for e in events if e.event_type == "z_spike"]
        assert len(spike_events) == 1
        assert spike_events[0].z_score == pytest.approx(-2.7)


class TestIdempotency:
    def test_running_detect_events_twice_does_not_duplicate(self) -> None:
        """detect_events is idempotent: upsert on conflict means same event_key is reused."""
        z_scores = {"port_calls": {"z_30d": 3.5, "z_90d": 3.0}}
        feature_values = {"port_calls": 150.0}
        baseline_values = {"port_calls": {"mean_30d": 80.0, "stdev_30d": 10.0}}
        snap = _make_snapshot(
            z_scores=z_scores,
            feature_values=feature_values,
            baseline_values=baseline_values,
        )
        session = _make_session()

        events1 = detect_events(session, snap, prev_severity=None)
        events2 = detect_events(session, snap, prev_severity=None)

        # Both runs produce the same number of events (same event_keys → upsert)
        spike1 = [e for e in events1 if e.event_type == "z_spike"]
        spike2 = [e for e in events2 if e.event_type == "z_spike"]
        assert len(spike1) == len(spike2)

        # Event keys are identical
        keys1 = {e.event_key for e in spike1}
        keys2 = {e.event_key for e in spike2}
        assert keys1 == keys2


class TestSeverityStepUp:
    def test_severity_step_up_emitted_when_severity_increases(self) -> None:
        snap = _make_snapshot(severity="high", z_scores={})
        session = _make_session()

        events = detect_events(session, snap, prev_severity="low")

        step_events = [e for e in events if e.event_type == "severity_step_up"]
        assert len(step_events) == 1
        assert step_events[0].severity == "high"
        assert step_events[0].attention_level == "high"
        assert step_events[0].confidence == pytest.approx(0.8)

    def test_no_step_up_when_severity_unchanged(self) -> None:
        snap = _make_snapshot(severity="high", z_scores={})
        session = _make_session()

        events = detect_events(session, snap, prev_severity="high")
        step_events = [e for e in events if e.event_type == "severity_step_up"]
        assert len(step_events) == 0

    def test_severity_step_down_emitted_when_severity_decreases(self) -> None:
        snap = _make_snapshot(severity="low", z_scores={})
        session = _make_session()

        events = detect_events(session, snap, prev_severity="high")
        step_events = [e for e in events if e.event_type == "severity_step_down"]
        assert len(step_events) == 1
        assert step_events[0].severity == "low"
        assert step_events[0].attention_level == "low"

    def test_no_step_event_when_prev_severity_none(self) -> None:
        """No step event when there is no previous severity (first observation)."""
        snap = _make_snapshot(severity="critical", z_scores={})
        session = _make_session()

        events = detect_events(session, snap, prev_severity=None)
        step_events = [
            e for e in events
            if e.event_type in ("severity_step_up", "severity_step_down")
        ]
        assert len(step_events) == 0


class TestSustainedStreak:
    def _make_metric_row(self, value: float) -> MagicMock:
        row = MagicMock()
        row.metric_value = value
        row.observed_at = datetime(2024, 1, 10, tzinfo=timezone.utc)
        return row

    def test_streak_emitted_when_5_days_above_mean(self) -> None:
        baseline_values = {"port_calls": {"mean_30d": 50.0, "stdev_30d": 10.0}}
        snap = _make_snapshot(
            z_scores={"port_calls": {"z_30d": 1.5, "z_90d": 1.0}},
            feature_values={"port_calls": 70.0},
            baseline_values=baseline_values,
        )
        # 5 rows all above mean of 50
        streak_rows = [self._make_metric_row(v) for v in [60, 65, 70, 62, 68]]

        session = _make_session(streak_rows=streak_rows)

        events = detect_events(session, snap, prev_severity=None)
        streak_events = [e for e in events if e.event_type == "sustained_streak"]
        assert len(streak_events) == 1
        assert streak_events[0].metric == "port_calls"
        assert streak_events[0].attention_level == "medium"
        assert streak_events[0].confidence == pytest.approx(0.7)

    def test_no_streak_when_fewer_than_5_days(self) -> None:
        baseline_values = {"port_calls": {"mean_30d": 50.0, "stdev_30d": 10.0}}
        snap = _make_snapshot(
            z_scores={},
            feature_values={"port_calls": 70.0},
            baseline_values=baseline_values,
        )
        streak_rows = [self._make_metric_row(v) for v in [60, 65]]
        session = _make_session(streak_rows=streak_rows)

        events = detect_events(session, snap, prev_severity=None)
        streak_events = [e for e in events if e.event_type == "sustained_streak"]
        assert len(streak_events) == 0

    def test_no_streak_when_values_mixed(self) -> None:
        """Mixed above/below mean → no streak."""
        baseline_values = {"port_calls": {"mean_30d": 50.0, "stdev_30d": 10.0}}
        snap = _make_snapshot(
            z_scores={},
            feature_values={"port_calls": 60.0},
            baseline_values=baseline_values,
        )
        # Mix of above and below mean
        streak_rows = [self._make_metric_row(v) for v in [60, 40, 70, 55, 65]]
        session = _make_session(streak_rows=streak_rows)

        events = detect_events(session, snap, prev_severity=None)
        streak_events = [e for e in events if e.event_type == "sustained_streak"]
        assert len(streak_events) == 0
