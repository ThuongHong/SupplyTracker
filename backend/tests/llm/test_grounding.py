"""Tests for build_entity_grounding and _normalise_entity_context."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.llm.chat import _normalise_entity_context
from app.llm.grounding import build_entity_grounding

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_risk_row(entity_name: str = "Singapore", score: float = 0.62, severity: str = "medium") -> MagicMock:
    row = MagicMock()
    row.entity_name = entity_name
    row.score = score
    row.severity = severity
    row.as_of = datetime(2026, 5, 1, tzinfo=UTC)
    return row


def _make_generic_session(risk_row=None):
    """
    Build a mock SQLAlchemy session that chains arbitrarily.

    The grounding code uses:
      - .first()    for latest risk score and most per-entity queries
      - .one()      for aggregate queries (avg, max)
      - .all()      for disruptions, events
      - .scalar()   for chokepoint vessel count aggregate
      - .limit().all()  for recent events

    We use side_effect on .first() to return the risk_row for the first call,
    then None for subsequent calls (so no congestion / chokepoint data fires).
    For .one() we return a tuple (avg, max) so the grounding doesn't crash when
    it does stats_30d[0] / stats_30d[1].
    """
    session = MagicMock()
    q = MagicMock()

    # Make the chain return q itself so arbitrary attribute access keeps chaining
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.group_by.return_value = q
    q.offset.return_value = q

    # .one() used for aggregate queries; return a 2-tuple (avg, max)
    q.one.return_value = (0.62, 0.83)

    # .all() → empty list (no disruptions, no events)
    q.all.return_value = []

    # .scalar() → None
    q.scalar.return_value = None

    # .one_or_none() → None
    q.one_or_none.return_value = None

    # .first() returns risk_row on first call, then None for all subsequent calls
    # so that Port lookup / PortCongestion / etc. return nothing and skip those branches
    first_calls = [0]

    def _first_side_effect():
        first_calls[0] += 1
        if first_calls[0] == 1:
            return risk_row
        return None

    q.first.side_effect = _first_side_effect

    session.query.return_value = q
    session.execute.return_value = MagicMock(
        fetchall=lambda: [],
        fetchone=lambda: None,
    )
    return session


# ---------------------------------------------------------------------------
# 3.5 — Snapshot: build_entity_grounding for a mock port
# ---------------------------------------------------------------------------


class TestBuildEntityGrounding:
    def test_port_grounding_contains_entity_name_and_risk_score(self):
        """3.5: build_entity_grounding output contains entity name and risk score."""
        risk_row = _make_risk_row(entity_name="Singapore", score=0.62, severity="medium")
        session = _make_generic_session(risk_row=risk_row)

        entity = {"entity_type": "port", "entity_id": "SGSIN"}
        result = build_entity_grounding(session, entity)

        assert isinstance(result, str)
        assert len(result) > 0

        # Entity name should appear in the output
        assert "Singapore" in result, f"Expected 'Singapore' in grounding output:\n{result}"

        # Risk score should appear (formatted to 2 decimal places)
        assert "0.62" in result, f"Expected risk score '0.62' in grounding output:\n{result}"

    def test_port_grounding_missing_entity_info_returns_skip_message(self):
        """3.5 edge: missing type/id returns a skip message rather than crashing."""
        session = _make_generic_session(risk_row=None)

        result = build_entity_grounding(session, {})

        assert "skipped" in result.lower()

    def test_port_grounding_no_risk_data_says_no_data(self):
        """3.5 edge: when there is no risk row, output includes 'no data available'."""
        session = _make_generic_session(risk_row=None)

        entity = {"entity_type": "port", "entity_id": "SGSIN"}
        result = build_entity_grounding(session, entity)

        assert "no data" in result.lower(), f"Expected 'no data' in grounding output:\n{result}"


# ---------------------------------------------------------------------------
# 3.6a — _normalise_entity_context wraps single dict in list
# ---------------------------------------------------------------------------


class TestNormaliseEntityContext:
    def test_wraps_single_dict_in_list(self):
        """3.6a: _normalise_entity_context wraps a single dict in a list."""
        single = {"entity_type": "port", "entity_id": "SGSIN"}
        result = _normalise_entity_context(single)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] is single

    def test_passes_list_through_unchanged(self):
        """3.6b: _normalise_entity_context passes a list through unchanged."""
        items = [
            {"entity_type": "port", "entity_id": "SGSIN"},
            {"entity_type": "chokepoint", "entity_id": "strait_of_hormuz"},
        ]
        result = _normalise_entity_context(items)

        assert result is items
        assert len(result) == 2
