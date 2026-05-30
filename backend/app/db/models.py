"""SQLAlchemy 2.0 ORM models — the kept tables from the SupplyChainWatch rebuild.

These mirror the table set retained for SupplyTracker after the slim-down.

# Removed: Vessel, VesselPosition, VesselWatchlist, VesselEnrichmentCache,
# TradeFlow, Anomaly — intentionally absent.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Port(Base):
    __tablename__ = "ports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # PortWatch business key (e.g. "port1188"). Stable identifier used as the
    # API path id and the metric entity_id; the int id stays for existing FKs.
    portid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    locode: Mapped[str | None] = mapped_column(String(16), index=True, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    country: Mapped[str] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geom: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    radius_km: Mapped[float] = mapped_column(Float, server_default="25.0")
    twenty_ft_eq_units_year: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_tracked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class Chokepoint(Base):
    __tablename__ = "chokepoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # PortWatch chokepoint business key (e.g. "chokepoint1").
    chokepointid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    geom: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POLYGON", srid=4326), nullable=False
    )
    is_tracked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class PortCongestion(Base):
    __tablename__ = "port_congestion"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    port_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ports.id"), primary_key=True
    )
    anchored_count: Mapped[int] = mapped_column(Integer)
    moored_count: Mapped[int] = mapped_column(Integer)
    underway_count: Mapped[int] = mapped_column(Integer)
    total_in_area: Mapped[int] = mapped_column(Integer)
    avg_dwell_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_speed: Mapped[float | None] = mapped_column(Float, nullable=True)


class ChokepointStatus(Base):
    __tablename__ = "chokepoint_status"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    chokepoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chokepoints.id"), primary_key=True
    )
    vessel_count: Mapped[int] = mapped_column(Integer)
    median_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class FreightIndex(Base):
    __tablename__ = "freight_index"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    index_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )


class BunkerPrice(Base):
    __tablename__ = "bunker_price"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    port_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    fuel_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    price_usd_per_ton: Mapped[float] = mapped_column(Float)


class PortWatchMetric(Base):
    __tablename__ = "port_watch_metric"

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(128))
    metric_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    metric_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_port_watch_metric_entity_metric_time",
            "entity_type",
            "entity_id",
            "metric_name",
            "observed_at",
        ),
    )


class PortRiskScore(Base):
    __tablename__ = "port_risk_score"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    port_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ports.id"), nullable=True
    )
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(128))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(16))
    component_scores: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    missing_components: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    reasons: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    source_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(16))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChokepointRiskScore(Base):
    __tablename__ = "chokepoint_risk_score"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    chokepoint_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("chokepoints.id"), nullable=True
    )
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(128))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(16))
    component_scores: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    missing_components: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    reasons: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    source_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(16))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskFeatureSnapshot(Base):
    __tablename__ = "risk_feature_snapshot"

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(128))
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    feature_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    baseline_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    z_scores: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    deltas: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    missing_features: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    source_freshness: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    driver_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    feature_schema_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )


class RiskStoryEvent(Base):
    __tablename__ = "risk_story_event"

    event_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    entity_type: Mapped[str] = mapped_column(String(16), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_name: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    metric: Mapped[str] = mapped_column(String(64))
    observed: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected: Mapped[float | None] = mapped_column(Float, nullable=True)
    z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    percent_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    drivers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    narrative: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    attention_level: Mapped[str] = mapped_column(String(16))
    data_sufficiency: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_risk_story_event_entity_time",
            "entity_type",
            "entity_id",
            "event_time",
        ),
    )


class EntityRiskForecast(Base):
    __tablename__ = "entity_risk_forecast"

    forecast_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(16), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_name: Mapped[str] = mapped_column(String(128))
    horizon_days: Mapped[int] = mapped_column(Integer)
    predictions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    confidence: Mapped[float] = mapped_column(Float)
    train_window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    train_window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_sufficiency_status: Mapped[str] = mapped_column(String(32))
    unavailable_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    key_drivers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    model_name: Mapped[str] = mapped_column(String(64))
    model_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    feature_schema_version: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        Index(
            "ix_entity_risk_forecast_entity_created",
            "entity_type",
            "entity_id",
            "created_at",
        ),
    )


class Insight(Base):
    __tablename__ = "insight"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    narrative: Mapped[str] = mapped_column(Text)
    narrative_llm: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    narrative_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, server_default="0")
    event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    affected_entities: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    source_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    attention_level: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        Index("ix_insight_generated_at_desc", text("generated_at DESC")),
        Index("ix_insight_attention_level", "attention_level"),
    )


class DisruptionPropagation(Base):
    __tablename__ = "disruption_propagation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_entity_type: Mapped[str] = mapped_column(String(16))
    source_entity_id: Mapped[str] = mapped_column(String(64), index=True)
    source_entity_name: Mapped[str] = mapped_column(String(128))
    target_entity_type: Mapped[str] = mapped_column(String(16))
    target_entity_id: Mapped[str] = mapped_column(String(64), index=True)
    target_entity_name: Mapped[str] = mapped_column(String(128))
    route_lane: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    source_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    status: Mapped[str] = mapped_column(String(16))


class DataCoverage(Base):
    __tablename__ = "data_coverage"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(128))
    first_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_rows: Mapped[int] = mapped_column(Integer, server_default="0")
    expected_days: Mapped[int] = mapped_column(Integer, server_default="0")
    missing_days: Mapped[int] = mapped_column(Integer, server_default="0")
    freshness_status: Mapped[str] = mapped_column(String(16))
    last_collection_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )


class CollectionLog(Base):
    __tablename__ = "collection_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(32), index=True)
    rows_collected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    feature: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class NewsItem(Base):
    __tablename__ = "news_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(64))
    url_hash: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), server_default="en")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "url_hash", name="uq_news_item_entity_url"),
        Index("ix_news_item_entity_published_at", "entity_type", "entity_id", text("published_at DESC")),
    )


class EntitySummaryCache(Base):
    """Cached LLM-generated entity summary text, keyed by entity + window.

    Regenerated only on sync (new data); normal page loads reuse the stored
    text so we don't burn LLM calls on every view.
    """

    __tablename__ = "entity_summary_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(64))
    window: Mapped[str] = mapped_column(String(8))
    what_happened: Mapped[str] = mapped_column(Text)
    so_what: Mapped[str] = mapped_column(Text)
    to_do: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "window", name="uq_entity_summary_cache"
        ),
    )
