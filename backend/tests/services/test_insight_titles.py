"""Unit tests for human-readable insight titles."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.insights import _build_title


def _event(**overrides):
    base = dict(
        event_type="z_spike",
        entity_id="port1188",
        entity_name="Qingdao",
        metric="port_calls",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_zspike_title_uses_entity_name_and_humanized_metric():
    title = _build_title(_event())
    assert title == "Anomalous spike in port calls at Qingdao"
    assert "port1188" not in title
    assert "port_calls" not in title


def test_falls_back_to_entity_id_when_name_missing():
    title = _build_title(_event(entity_name=None))
    assert title == "Anomalous spike in port calls at port1188"


def test_severity_titles_use_entity_name():
    assert _build_title(_event(event_type="severity_step_up")) == (
        "Risk severity escalated at Qingdao"
    )
    assert _build_title(_event(event_type="severity_step_down")) == (
        "Risk severity reduced at Qingdao"
    )


def test_sustained_streak_humanizes_metric():
    title = _build_title(_event(event_type="sustained_streak", metric="import_volume"))
    assert title == "Sustained trend in import volume at Qingdao"
