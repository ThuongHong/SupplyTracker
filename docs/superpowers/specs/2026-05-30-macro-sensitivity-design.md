# Macro Sensitivity — per-entity lead-lag correlation

**Date:** 2026-05-30
**Status:** Approved (pending spec review)

## Problem

The macro indices (FBX, WCI, Brent) currently render as standalone charts with no
connection to PortWatch port/chokepoint activity. Users see global freight/oil
numbers but get no insight into how those moves relate to the trade of the entity
they are looking at. The macro panel feels useless because nothing ties it to the
port data.

## Goal

On a port's or chokepoint's detail page, surface how *that entity's* trade metrics
move with the macro indices, using a lead-lag correlation. Output is a short list
of plain-English insight lines such as:

> Brent leads port calls by 5d — moderate inverse (r=−0.58, n=24)

## Decisions (from brainstorming)

- **Insight type:** correlation with lead-lag scan (not just contemporaneous).
- **Unit:** per-entity (per port / per chokepoint), NOT an aggregate over all
  tracked ports. Aggregating an arbitrary user-picked basket washes out signal and
  is unstable as tracking changes.
- **Placement:** port/chokepoint detail "overview" tab (the congestion/port view),
  NOT the Overview dashboard.
- **Selection:** scan every macro × metric pair for the entity, rank by |r|, show
  top 3.
- **Max lag window:** 14 days (macro leading trade, k ∈ [0..14]).
- **Weak findings (|r| < 0.3):** shown but dimmed and labeled weak — card is always
  populated, but honest about strength.

## Data reality

- PortWatch metrics are **daily** (`port_watch_metric`, one row per `observed_at`).
- FRED Brent (`DCOILBRENTEU`) is daily; FBX/WCI seeded daily.
- Live FRED collector pulls only the last 30 observations (`limit=30`), so real
  macro history is shallow. Seeded dev data has the full window. Lag scan operates
  on whatever overlap exists and reports `n`.

Metrics per entity:
- **Port:** `port_calls`, `import_volume`, `export_volume`
- **Chokepoint:** `transit_calls`

Macro series: `FBX`, `WCI`, `DCOILBRENTEU` (labeled "Brent").

## Architecture

### New module: `backend/app/analysis/macro_correlation.py`

Pure, dependency-free functions (no DB, no ORM) so they are unit-testable in
isolation. Series are `list[{"time": iso, "value": float}]`.

```
align(a, b) -> tuple[list[float], list[float]]
    Inner-join two series on day (time[:10]); return paired x/y in date order.

pearson(xs, ys, min_n=10) -> float | None
    Pearson r. None if len < min_n or either series has zero variance.

best_lag(macro, metric, max_lag=14, min_overlap=10) -> tuple[float, int, int] | None
    For k in 0..max_lag, shift macro forward by k days (macro leads trade),
    align with metric, compute pearson. Return (r, lag_days, n) for the k with
    the largest |r| that meets min_overlap. None if no lag qualifies.

macro_sensitivity(macro_series_by_name, metric_series_by_name,
                  max_lag=14, top_k=3) -> list[Finding]
    Scan every (macro, metric) pair, run best_lag, collect findings, sort by |r|
    desc, return top_k.

Finding = {
    "macro": str,        # display label, e.g. "Brent"
    "metric": str,       # e.g. "port_calls"
    "r": float,
    "lag_days": int,
    "n": int,
    "strength": str,     # "weak" | "moderate" | "strong"
    "insight": str,      # composed plain-English line
}
```

**Strength buckets** (by |r|): `< 0.3` weak, `< 0.6` moderate, else strong.

**Insight phrasing:**
- direction = "inverse" if r < 0 else "positive"
- lag part: `lag_days == 0` → "moves with"; else "leads {metric} by {lag_days}d"
- e.g. `"Brent leads port calls by 5d — moderate inverse (r=−0.58, n=24)"`
- metric labels: `port_calls`→"port calls", `import_volume`→"import volume",
  `export_volume`→"export volume", `transit_calls`→"transit calls".
- macro labels: `DCOILBRENTEU`→"Brent", others as-is.

### Schema: `backend/app/schemas/dashboard.py`

```python
class MacroCorrelation(BaseModel):
    macro: str
    metric: str
    r: float
    lag_days: int
    n: int
    strength: str
    insight: str

class DashboardResponse(BaseModel):
    ...
    macro_sensitivity: list[MacroCorrelation] = []
```

### Service: `backend/app/services/dashboard.py`

- Add helper `_macro_series_by_name(session, since) -> dict[str, list[series]]`
  pulling each `FreightIndex.index_name` as its own `{time,value}` series (the
  existing `_build_indices_chart` merges them into one per-time dict, which is the
  wrong shape for correlation).
- In `build_dashboard`: build metric series for the three port metrics, call
  `macro_sensitivity`, attach to `DashboardResponse.macro_sensitivity`.
- In `build_chokepoint_dashboard`: same with `transit_calls` (single metric).
- `throughput`/`transit_volume` series are already built; reuse where possible.

### Frontend

- `frontend/src/api/types.ts`: add `MacroCorrelation` type; add
  `macro_sensitivity?: MacroCorrelation[]` to the dashboard response type.
- New component `frontend/src/components/MacroSensitivity.tsx`: renders the list of
  insight lines. Direction color (inverse vs positive), weak findings dimmed
  (reduced opacity + "weak" tag). Empty/short → "Not enough overlapping history to
  correlate with macro indices yet."
- Mount as a new `Card title="Macro sensitivity"` in:
  - `PortDetailView.tsx` overview tab
  - `ChokepointDetailView.tsx` overview tab

## Error / edge handling

- No macro data or no metric data → `macro_sensitivity = []` → card shows empty
  message.
- Overlap < `min_overlap` for every lag of a pair → that pair contributes nothing.
- Zero variance (flat series) → `pearson` returns None → pair skipped.
- NaN guard: skip non-finite values during alignment.

## Testing (TDD — pure module first)

`backend/tests/analysis/test_macro_correlation.py`:
- `pearson` on known vectors (perfect +1, perfect −1, zero-corr) within tolerance.
- `pearson` returns None below `min_n` and on zero-variance input.
- `align` on misaligned/overlapping dates returns only the intersection, in order.
- `best_lag` recovers a known lag from a synthetically shifted series.
- `macro_sensitivity` ranks by |r| and respects `top_k`.
- Insufficient overlap everywhere → empty list.

Service-level: extend `backend/tests/api/test_dashboard.py` to assert the
`macro_sensitivity` field is present and well-formed for a seeded port.

## YAGNI / out of scope

- No 3×3 heatmap or full-matrix table.
- No Overview dashboard changes.
- No p-value / significance test (sample size `n` is surfaced instead).
- No cross-port ranking (per-entity only).
