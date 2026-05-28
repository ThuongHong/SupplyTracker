"""Alembic environment configuration.

Uses the application's lazy engine (get_engine) for online migrations and
falls back to DATABASE_URL for offline SQL generation.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool

from alembic import context

# ---------------------------------------------------------------------------
# Make sure 'app' package is importable when alembic is run from backend/.
# ---------------------------------------------------------------------------
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# ---------------------------------------------------------------------------
# Import Base and populate metadata by importing all models.
# ---------------------------------------------------------------------------
from app.db.session import Base, get_engine  # noqa: E402
import app.db.models  # noqa: F401, E402 — side-effect: registers all models on Base.metadata

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Alembic config object.
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_url() -> str:
    """Return the database URL, preferring the environment variable."""
    return os.environ.get(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url", ""),
    )


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emit SQL to stdout, no DB connection)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include object-level comparison so PostGIS / TimescaleDB columns
        # are compared by type, not just name.
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode using the application's shared engine."""
    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # NullPool is used implicitly because we borrow the app engine,
            # which already manages its own pool.
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
