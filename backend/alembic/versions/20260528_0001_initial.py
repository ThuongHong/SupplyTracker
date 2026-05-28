"""initial

Revision ID: 0001
Revises:
Create Date: 2026-05-28 00:00:00.000000

Creates all 17 application tables, enables TimescaleDB hypertables on the
7 time-series tables, and adds supplementary indices.

Extensions (timescaledb, postgis, pg_trgm) are created by
docker/postgres/init.sql and are assumed to already exist when this
migration runs.
"""
from __future__ import annotations

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. ports  (no FKs — must be first)
    # ------------------------------------------------------------------
    op.create_table(
        "ports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("locode", sa.String(16), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("country", sa.String(64), nullable=False),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column(
            "radius_km",
            sa.Float(),
            server_default="25.0",
            nullable=False,
        ),
        sa.Column("twenty_ft_eq_units_year", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ports_locode"), "ports", ["locode"], unique=False)

    # ------------------------------------------------------------------
    # 2. chokepoints  (no FKs — must be before chokepoint_* tables)
    # ------------------------------------------------------------------
    op.create_table(
        "chokepoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(geometry_type="POLYGON", srid=4326),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ------------------------------------------------------------------
    # 3. port_congestion  — hypertable, partition by `time`
    # ------------------------------------------------------------------
    op.create_table(
        "port_congestion",
        sa.Column(
            "time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "port_id",
            sa.Integer(),
            sa.ForeignKey("ports.id"),
            nullable=False,
        ),
        sa.Column("anchored_count", sa.Integer(), nullable=False),
        sa.Column("moored_count", sa.Integer(), nullable=False),
        sa.Column("underway_count", sa.Integer(), nullable=False),
        sa.Column("total_in_area", sa.Integer(), nullable=False),
        sa.Column("avg_dwell_hours", sa.Float(), nullable=True),
        sa.Column("median_speed", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("time", "port_id"),
    )

    # ------------------------------------------------------------------
    # 4. chokepoint_status  — hypertable, partition by `time`
    # ------------------------------------------------------------------
    op.create_table(
        "chokepoint_status",
        sa.Column(
            "time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "chokepoint_id",
            sa.Integer(),
            sa.ForeignKey("chokepoints.id"),
            nullable=False,
        ),
        sa.Column("vessel_count", sa.Integer(), nullable=False),
        sa.Column("median_speed", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("time", "chokepoint_id"),
    )

    # ------------------------------------------------------------------
    # 5. freight_index  — hypertable, partition by `time`
    # ------------------------------------------------------------------
    op.create_table(
        "freight_index",
        sa.Column(
            "time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("index_name", sa.String(64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.PrimaryKeyConstraint("time", "index_name"),
    )

    # ------------------------------------------------------------------
    # 6. bunker_price  — hypertable, partition by `time`
    # ------------------------------------------------------------------
    op.create_table(
        "bunker_price",
        sa.Column(
            "time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("port_code", sa.String(16), nullable=False),
        sa.Column("fuel_type", sa.String(16), nullable=False),
        sa.Column("price_usd_per_ton", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("time", "port_code", "fuel_type"),
    )

    # ------------------------------------------------------------------
    # 7. port_watch_metric  — hypertable, partition by `observed_at`
    # ------------------------------------------------------------------
    op.create_table(
        "port_watch_metric",
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("entity_name", sa.String(128), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_entity_id", sa.String(64), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint(
            "observed_at", "entity_type", "entity_id", "metric_name", "source"
        ),
    )
    op.create_index(
        "ix_port_watch_metric_entity_metric_time",
        "port_watch_metric",
        ["entity_type", "entity_id", "metric_name", "observed_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 8. port_risk_score  — hypertable, partition by `time`
    # ------------------------------------------------------------------
    op.create_table(
        "port_risk_score",
        sa.Column(
            "time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "port_id",
            sa.Integer(),
            sa.ForeignKey("ports.id"),
            nullable=True,
        ),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("entity_name", sa.String(128), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column(
            "component_scores",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("missing_components", JSONB, nullable=True),
        sa.Column("reasons", JSONB, nullable=True),
        sa.Column("source_metrics", JSONB, nullable=True),
        sa.Column("freshness_status", sa.String(16), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("time", "entity_id"),
    )

    # ------------------------------------------------------------------
    # 9. chokepoint_risk_score  — hypertable, partition by `time`
    # ------------------------------------------------------------------
    op.create_table(
        "chokepoint_risk_score",
        sa.Column(
            "time", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "chokepoint_id",
            sa.Integer(),
            sa.ForeignKey("chokepoints.id"),
            nullable=True,
        ),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("entity_name", sa.String(128), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column(
            "component_scores",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("missing_components", JSONB, nullable=True),
        sa.Column("reasons", JSONB, nullable=True),
        sa.Column("source_metrics", JSONB, nullable=True),
        sa.Column("freshness_status", sa.String(16), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("time", "entity_id"),
    )

    # ------------------------------------------------------------------
    # 10. risk_feature_snapshot
    # ------------------------------------------------------------------
    op.create_table(
        "risk_feature_snapshot",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("entity_name", sa.String(128), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column(
            "feature_values",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "baseline_values",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "z_scores",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "deltas",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("missing_features", JSONB, nullable=True),
        sa.Column("source_freshness", JSONB, nullable=True),
        sa.Column("driver_metadata", JSONB, nullable=True),
        sa.Column("feature_schema_version", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("snapshot_date", "entity_type", "entity_id"),
    )

    # ------------------------------------------------------------------
    # 11. risk_story_event
    # ------------------------------------------------------------------
    op.create_table(
        "risk_story_event",
        sa.Column("event_key", sa.String(128), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("entity_name", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("observed", sa.Float(), nullable=True),
        sa.Column("expected", sa.Float(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("percent_change", sa.Float(), nullable=True),
        sa.Column("drivers", JSONB, nullable=True),
        sa.Column("source_metrics", JSONB, nullable=True),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("attention_level", sa.String(16), nullable=False),
        sa.Column("data_sufficiency", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("event_key"),
    )
    op.create_index(
        op.f("ix_risk_story_event_event_time"),
        "risk_story_event",
        ["event_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_story_event_entity_type"),
        "risk_story_event",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_story_event_entity_id"),
        "risk_story_event",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_story_event_entity_time",
        "risk_story_event",
        ["entity_type", "entity_id", "event_time"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 12. entity_risk_forecast
    # ------------------------------------------------------------------
    op.create_table(
        "entity_risk_forecast",
        sa.Column("forecast_key", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("entity_name", sa.String(128), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column(
            "predictions",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("train_window_start", sa.Date(), nullable=True),
        sa.Column("train_window_end", sa.Date(), nullable=True),
        sa.Column("data_sufficiency_status", sa.String(32), nullable=False),
        sa.Column("unavailable_reason", sa.String(128), nullable=True),
        sa.Column("key_drivers", JSONB, nullable=True),
        sa.Column(
            "metrics",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("model_params", JSONB, nullable=True),
        sa.Column("feature_schema_version", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("forecast_key"),
    )
    op.create_index(
        op.f("ix_entity_risk_forecast_created_at"),
        "entity_risk_forecast",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entity_risk_forecast_entity_type"),
        "entity_risk_forecast",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entity_risk_forecast_entity_id"),
        "entity_risk_forecast",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_entity_risk_forecast_entity_created",
        "entity_risk_forecast",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 13. insight
    # ------------------------------------------------------------------
    op.create_table(
        "insight",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("narrative_llm", sa.Text(), nullable=True),
        sa.Column("narrative_model", sa.String(64), nullable=True),
        sa.Column(
            "narrative_generated_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column(
            "priority", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("event_type", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("affected_entities", JSONB, nullable=True),
        sa.Column("source_metrics", JSONB, nullable=True),
        sa.Column("attention_level", sa.String(16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX ix_insight_generated_at_desc ON insight (generated_at DESC)"
    )
    op.create_index(
        "ix_insight_attention_level",
        "insight",
        ["attention_level"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 14. disruption_propagation
    # ------------------------------------------------------------------
    op.create_table(
        "disruption_propagation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_entity_type", sa.String(16), nullable=False),
        sa.Column("source_entity_id", sa.String(64), nullable=False),
        sa.Column("source_entity_name", sa.String(128), nullable=False),
        sa.Column("target_entity_type", sa.String(16), nullable=False),
        sa.Column("target_entity_id", sa.String(64), nullable=False),
        sa.Column("target_entity_name", sa.String(128), nullable=False),
        sa.Column("route_lane", sa.String(128), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_metrics", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_disruption_propagation_source_entity_id"),
        "disruption_propagation",
        ["source_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_disruption_propagation_target_entity_id"),
        "disruption_propagation",
        ["target_entity_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 15. data_coverage
    # ------------------------------------------------------------------
    op.create_table(
        "data_coverage",
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("entity_name", sa.String(128), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "latest_observed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "observed_rows", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "expected_days", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "missing_days", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("freshness_status", sa.String(16), nullable=False),
        sa.Column("last_collection_status", sa.String(32), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("metadata", JSONB, nullable=True),
        sa.PrimaryKeyConstraint("source", "entity_type", "entity_id"),
    )

    # ------------------------------------------------------------------
    # 16. collection_log
    # ------------------------------------------------------------------
    op.create_table(
        "collection_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("rows_collected", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_collection_log_started_at"),
        "collection_log",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_log_source"),
        "collection_log",
        ["source"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 17. llm_usage_log
    # ------------------------------------------------------------------
    op.create_table(
        "llm_usage_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("feature", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_llm_usage_log_timestamp"),
        "llm_usage_log",
        ["timestamp"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # TimescaleDB hypertables
    # All 7 time-series tables — if_not_exists keeps upgrades idempotent.
    # ------------------------------------------------------------------
    op.execute(
        "SELECT create_hypertable('port_watch_metric', 'observed_at', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('freight_index', 'time', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('bunker_price', 'time', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('port_congestion', 'time', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('chokepoint_status', 'time', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('port_risk_score', 'time', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('chokepoint_risk_score', 'time', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    # TimescaleDB hypertables are plain tables from Postgres' perspective
    # and drop via the same DROP TABLE.

    op.drop_table("llm_usage_log")
    op.drop_table("collection_log")
    op.drop_table("data_coverage")
    op.drop_table("disruption_propagation")
    op.drop_table("insight")
    op.drop_table("entity_risk_forecast")
    op.drop_table("risk_story_event")
    op.drop_table("risk_feature_snapshot")
    op.drop_table("chokepoint_risk_score")
    op.drop_table("port_risk_score")
    op.drop_table("port_watch_metric")
    op.drop_table("bunker_price")
    op.drop_table("freight_index")
    op.drop_table("chokepoint_status")
    op.drop_table("port_congestion")
    op.drop_table("chokepoints")
    op.drop_table("ports")
