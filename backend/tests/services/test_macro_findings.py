from __future__ import annotations

from app.schemas.dashboard import MacroCorrelation
from app.services.dashboard import _macro_findings


def _series(values: list[float]) -> list[dict[str, float]]:
    return [{"time": f"2026-01-{i + 1:02d}T00:00:00+00:00", "value": v} for i, v in enumerate(values)]


def test_maps_findings_to_schema() -> None:
    n = 14
    up = _series([float(i) for i in range(n)])
    down = _series([float(n - i) for i in range(n)])
    out = _macro_findings({"DCOILBRENTEU": up}, {"port_calls": down})
    assert out and isinstance(out[0], MacroCorrelation)
    assert out[0].macro == "Brent"
    assert out[0].metric == "port_calls"
    assert out[0].strength == "strong"


def test_empty_when_no_data() -> None:
    assert _macro_findings({}, {"port_calls": _series([1.0, 2.0])}) == []
