from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services.disruption import LANE_PORTS, propagate_chokepoint_event
from app.db.models import RiskStoryEvent


def _make_event(
    entity_id: str = "hormuz",
    entity_type: str = "chokepoint",
    entity_name: str = "Strait of Hormuz",
    event_type: str = "z_spike",
    severity: str = "high",
    confidence: float = 0.9,
) -> RiskStoryEvent:
    event = RiskStoryEvent(
        event_key=f"{entity_type}:{entity_id}:2024-01-15:z_spike:",
        event_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        event_type=event_type,
        severity=severity,
        metric="transit_calls",
        observed=30.0,
        expected=60.0,
        z_score=-3.0,
        percent_change=-50.0,
        narrative="Test narrative",
        confidence=confidence,
        attention_level="high",
    )
    return event


def _make_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    return session


class TestPropagateChokepointEvent:
    def test_high_severity_propagates_to_lane_ports(self) -> None:
        """A 'high' severity chokepoint event propagates to all mapped lane ports."""
        event = _make_event(entity_id="hormuz", severity="high")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        expected_ports = LANE_PORTS["hormuz"]
        assert len(result) == len(expected_ports)
        target_ids = {r.target_entity_id for r in result}
        assert target_ids == set(expected_ports)

    def test_critical_severity_also_propagates(self) -> None:
        """A 'critical' severity event is also propagated."""
        event = _make_event(entity_id="suez", severity="critical")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        expected_ports = LANE_PORTS["suez"]
        assert len(result) == len(expected_ports)

    def test_low_severity_does_not_propagate(self) -> None:
        """A 'low' severity event must NOT be propagated."""
        event = _make_event(entity_id="hormuz", severity="low")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        assert result == []
        session.add.assert_not_called()

    def test_elevated_severity_does_not_propagate(self) -> None:
        """An 'elevated' severity event (not high/critical) is not propagated."""
        event = _make_event(entity_id="malacca", severity="elevated")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        assert result == []

    def test_propagation_row_has_correct_fields(self) -> None:
        """Check that a propagated row has the expected source/lane/severity fields."""
        event = _make_event(entity_id="malacca", severity="high")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        assert len(result) > 0
        row = result[0]
        assert row.source_entity_type == "chokepoint"
        assert row.source_entity_id == "malacca"
        assert row.route_lane == "malacca"
        assert row.severity == "high"
        assert row.status == "active"
        assert row.confidence == pytest.approx(0.9)

    def test_unknown_chokepoint_returns_empty(self) -> None:
        """A chokepoint not in the lane map produces no propagations."""
        event = _make_event(entity_id="unknown_strait_xyz", severity="high")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        assert result == []

    def test_session_add_called_for_each_downstream_port(self) -> None:
        """session.add() must be called once per downstream port."""
        event = _make_event(entity_id="suez", severity="high")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        assert session.add.call_count == len(LANE_PORTS["suez"])
        session.flush.assert_called_once()

    def test_case_insensitive_entity_id_matching(self) -> None:
        """entity_id matching is case-insensitive."""
        event = _make_event(entity_id="HORMUZ", severity="high")
        session = _make_session()

        result = propagate_chokepoint_event(session, event)

        assert len(result) == len(LANE_PORTS["hormuz"])
