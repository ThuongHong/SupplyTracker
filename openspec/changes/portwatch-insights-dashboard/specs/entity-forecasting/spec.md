## ADDED Requirements

### Requirement: Short-horizon forecasts per entity
The system SHALL produce a 14-day forecast of each tracked entity's primary throughput metric (e.g., port: `port_calls`; chokepoint: `transit_calls`) at least daily and persist results to `EntityRiskForecast`.

#### Scenario: Forecast row written
- **WHEN** the `generate_forecasts` task runs for entity `port:USLAX`
- **THEN** a row exists with `horizon_days=14`, `predictions` containing 14 dated points each with `value` and `low`/`high` quantiles, and `model_name` set

### Requirement: Data sufficiency gating
The system SHALL refuse to produce a forecast when fewer than 60 days of history are available, instead writing a row with `data_sufficiency_status="insufficient"`, `unavailable_reason` populated, and `predictions=[]`.

#### Scenario: Newly added port
- **WHEN** a port has only 20 observed days
- **THEN** the forecast row has `predictions=[]`, `confidence=0`, `data_sufficiency_status="insufficient"`, and `unavailable_reason="history_lt_60_days"`

### Requirement: Forecast metrics and drivers
The system SHALL record backtest metrics (`mape`, `smape`, `coverage_80`) in `metrics` and SHALL list the top 3 contributing features in `key_drivers` when the model supports feature attribution.

#### Scenario: Metrics recorded
- **WHEN** a forecast is produced from a sufficient history
- **THEN** `metrics.mape`, `metrics.smape`, and `metrics.coverage_80` are floats, and `key_drivers` is a list of at most 3 strings

### Requirement: Forecast freshness
The system SHALL stamp `created_at` and `train_window_end` on every forecast row and the API SHALL only surface forecasts whose `created_at` is within the last 48 hours.

#### Scenario: Stale forecast hidden
- **WHEN** a forecast row is 72 hours old and a fresher one does not exist
- **THEN** `GET /api/v1/risk/forecasts/<entity>` returns `{ "status": "stale", "data": null }`
