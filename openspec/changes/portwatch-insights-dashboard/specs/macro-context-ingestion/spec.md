## ADDED Requirements

### Requirement: Freight index collection
The system SHALL collect Freightos Baltic Index (FBX) and Drewry World Container Index (WCI) values at least daily and persist them into `FreightIndex` keyed on `(time, index_name)`.

#### Scenario: Daily FBX/WCI refresh
- **WHEN** the `collect_freight_indices` task runs after the publishing window
- **THEN** the latest available value for each tracked lane is upserted into `FreightIndex` with `source` set to the scraper name and `metadata_` carrying lane/route metadata

### Requirement: FRED macro series collection
The system SHALL collect a configurable list of FRED macro series (e.g., Brent crude, US PPI for water transportation) via the FRED API at least daily and persist them into `FreightIndex` with `source="fred"` and `index_name` set to the FRED series ID.

#### Scenario: FRED series refresh
- **WHEN** the `collect_fred` task runs with `FRED_SERIES=["DCOILBRENTEU","PCU4831204831204"]`
- **THEN** each series' new observations are upserted and missing API keys are surfaced as a configuration error in `CollectionLog.error`

### Requirement: Bunker price collection
The system SHALL collect bunker fuel prices for a configurable set of ports and fuel types daily and persist them into `BunkerPrice` keyed on `(time, port_code, fuel_type)`.

#### Scenario: Bunker scrape
- **WHEN** the `collect_bunker_prices` task runs for `("SGSIN","VLSFO")`, `("AEFJR","VLSFO")`, `("NLRTM","VLSFO")`
- **THEN** each triple has a row written with `price_usd_per_ton` and a non-null `time`

### Requirement: Macro context API exposure
The system SHALL expose macro context series via the insights API so the frontend Macro Indices page can render timeseries and current values without recomputation.

#### Scenario: Indices list endpoint
- **WHEN** a client calls `GET /api/v1/indices`
- **THEN** the response includes every tracked freight index and FRED series with `name`, `latest_value`, `latest_time`, `change_pct_7d`, and `change_pct_30d`
