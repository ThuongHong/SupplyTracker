"""add entity_summary_cache

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-31 00:05:00.000000

Caches the LLM-generated entity summary (what_happened / so_what / to_do) per
entity + window, so it is regenerated only on sync rather than on every load.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_summary_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("window", sa.String(length=8), nullable=False),
        sa.Column("what_happened", sa.Text(), nullable=False),
        sa.Column("so_what", sa.Text(), nullable=False),
        sa.Column("to_do", sa.Text(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "entity_type", "entity_id", "window", name="uq_entity_summary_cache"
        ),
    )


def downgrade() -> None:
    op.drop_table("entity_summary_cache")
