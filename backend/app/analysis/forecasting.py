from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import EntityRiskForecast, PortWatchMetric

_SCHEMA_VERSION = "1.0"
_MODEL_NAME = "AutoETS"


def _smape(actual: list[float], predicted: list[float]) -> float:
    """Symmetric mean absolute percentage error."""
    if not actual:
        return 0.0
    errors = []
    for a, p in zip(actual, predicted):
        denom = (abs(a) + abs(p)) / 2
        if denom > 0:
            errors.append(abs(a - p) / denom)
    return float(sum(errors) / len(errors)) if errors else 0.0


def generate_forecast(
    session: Session,
    entity_type: str,
    entity_id: str,
    entity_name: str,
    metric_name: str,
    horizon_days: int = 14,
) -> EntityRiskForecast:
    """Fit AutoETS on historical PortWatchMetric data and upsert EntityRiskForecast.

    Returns the upserted EntityRiskForecast row (detached).
    If fewer than 60 rows exist, returns an insufficient-data record.
    """
    today = date.today()
    forecast_key = f"{entity_type}:{entity_id}:{metric_name}:{today.isoformat()}"

    # Query all historical rows ordered by observed_at
    all_rows = (
        session.query(PortWatchMetric)
        .filter(
            PortWatchMetric.entity_type == entity_type,
            PortWatchMetric.entity_id == entity_id,
            PortWatchMetric.metric_name == metric_name,
        )
        .order_by(PortWatchMetric.observed_at.asc())
        .all()
    )

    def _build_insufficient(reason: str) -> EntityRiskForecast:
        row = EntityRiskForecast(
            forecast_key=forecast_key,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            horizon_days=horizon_days,
            predictions=[],
            confidence=0.0,
            data_sufficiency_status="insufficient",
            unavailable_reason=reason,
            key_drivers=[],
            metrics={},
            model_name=_MODEL_NAME,
            feature_schema_version=_SCHEMA_VERSION,
        )
        stmt = (
            pg_insert(EntityRiskForecast)
            .values(
                forecast_key=forecast_key,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                horizon_days=horizon_days,
                predictions=[],
                confidence=0.0,
                data_sufficiency_status="insufficient",
                unavailable_reason=reason,
                key_drivers=[],
                metrics={},
                model_name=_MODEL_NAME,
                feature_schema_version=_SCHEMA_VERSION,
            )
            .on_conflict_do_update(
                index_elements=["forecast_key"],
                set_={
                    "data_sufficiency_status": "insufficient",
                    "unavailable_reason": reason,
                    "confidence": 0.0,
                    "predictions": [],
                },
            )
        )
        session.execute(stmt)
        session.flush()
        return row

    if len(all_rows) < 60:
        return _build_insufficient("history_lt_60_days")

    # Build time-indexed series, deduplicate by date (keep last)
    dates = pd.to_datetime([r.observed_at for r in all_rows]).normalize()
    values = [r.metric_value for r in all_rows]
    series = pd.Series(values, index=dates)
    series = series.groupby(series.index).last()
    series = series.sort_index()

    train_window_start: date = series.index[0].date()
    train_window_end: date = series.index[-1].date()

    # Prepare statsforecast DataFrame
    df = pd.DataFrame(
        {
            "ds": series.index,
            "y": series.values,
            "unique_id": [entity_id] * len(series),
        }
    )

    try:
        from statsforecast import StatsForecast
        from statsforecast.models import AutoETS

        sf = StatsForecast(models=[AutoETS()], freq="D", verbose=False)
        forecast_df = sf.forecast(df=df, h=horizon_days, level=[80])

        predictions: list[dict[str, Any]] = []
        for _, frow in forecast_df.iterrows():
            predictions.append(
                {
                    "date": str(frow["ds"].date() if hasattr(frow["ds"], "date") else frow["ds"]),
                    "value": float(frow["AutoETS"]),
                    "low": float(frow.get("AutoETS-lo-80", frow["AutoETS"])),
                    "high": float(frow.get("AutoETS-hi-80", frow["AutoETS"])),
                }
            )
    except Exception:
        return _build_insufficient("model_fit_failed")

    # Simple holdout backtest: last 14 days
    metrics_out: dict[str, Any] = {}
    if len(series) >= 14:
        holdout = series.iloc[-14:]
        train = series.iloc[:-14]
        try:
            df_train = pd.DataFrame(
                {
                    "ds": train.index,
                    "y": train.values,
                    "unique_id": [entity_id] * len(train),
                }
            )
            sf2 = StatsForecast(models=[AutoETS()], freq="D", verbose=False)
            bt_forecast = sf2.forecast(df=df_train, h=14)
            bt_pred = bt_forecast["AutoETS"].tolist()
            bt_actual = holdout.tolist()
            smape_val = _smape(bt_actual, bt_pred)
            metrics_out["smape_holdout_14d"] = smape_val
        except Exception:
            pass

    # Derive key_drivers: top 3 other metrics by absolute correlation with residuals
    key_drivers: list[str] = []
    try:
        # Collect other metrics for this entity
        other_metrics_rows = (
            session.query(PortWatchMetric.metric_name)
            .filter(
                PortWatchMetric.entity_type == entity_type,
                PortWatchMetric.entity_id == entity_id,
                PortWatchMetric.metric_name != metric_name,
            )
            .distinct()
            .all()
        )
        other_metrics = [r[0] for r in other_metrics_rows]

        if other_metrics and len(predictions) > 0:
            # Build residuals series from the training fit (approximate as actual - mean)
            train_mean = float(series.mean())
            residuals = series - train_mean

            corr_map: dict[str, float] = {}
            for om in other_metrics:
                om_rows = (
                    session.query(PortWatchMetric)
                    .filter(
                        PortWatchMetric.entity_type == entity_type,
                        PortWatchMetric.entity_id == entity_id,
                        PortWatchMetric.metric_name == om,
                    )
                    .order_by(PortWatchMetric.observed_at.asc())
                    .all()
                )
                if len(om_rows) < 5:
                    continue
                om_dates = pd.to_datetime([r.observed_at for r in om_rows]).normalize()
                om_vals = pd.Series([r.metric_value for r in om_rows], index=om_dates)
                om_vals = om_vals.groupby(om_vals.index).last().sort_index()

                # Align on common dates
                common = residuals.index.intersection(om_vals.index)
                if len(common) < 5:
                    continue
                corr = float(residuals[common].corr(om_vals[common]))
                if not pd.isna(corr):
                    corr_map[om] = abs(corr)

            key_drivers = sorted(corr_map, key=corr_map.get, reverse=True)[:3]  # type: ignore[arg-type]
    except Exception:
        pass

    # Confidence: 1 - smape (clamped to [0,1])
    smape_val_for_conf = metrics_out.get("smape_holdout_14d", 0.0)
    confidence = max(0.0, min(1.0, 1.0 - smape_val_for_conf))

    upsert_vals: dict[str, Any] = {
        "forecast_key": forecast_key,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "horizon_days": horizon_days,
        "predictions": predictions,
        "confidence": confidence,
        "train_window_start": train_window_start,
        "train_window_end": train_window_end,
        "data_sufficiency_status": "ok",
        "unavailable_reason": None,
        "key_drivers": key_drivers,
        "metrics": metrics_out,
        "model_name": _MODEL_NAME,
        "feature_schema_version": _SCHEMA_VERSION,
    }

    stmt = (
        pg_insert(EntityRiskForecast)
        .values(**upsert_vals)
        .on_conflict_do_update(
            index_elements=["forecast_key"],
            set_={k: v for k, v in upsert_vals.items() if k != "forecast_key"},
        )
    )
    session.execute(stmt)
    session.flush()

    return EntityRiskForecast(**upsert_vals)
