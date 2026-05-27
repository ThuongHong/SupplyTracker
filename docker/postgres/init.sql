-- Auto-run by timescale/timescaledb-ha:pg15 at first container start via
-- /docker-entrypoint-initdb.d/. Installs required extensions; Alembic
-- migrations (later bundles) create all tables.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
