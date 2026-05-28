"""add news_item table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-29 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("language", sa.String(8), server_default="en", nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type", "entity_id", "url_hash", name="uq_news_item_entity_url"
        ),
    )
    op.create_index(
        "ix_news_item_entity_published_at",
        "news_item",
        ["entity_type", "entity_id", sa.text("published_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_news_item_entity_published_at", table_name="news_item")
    op.drop_table("news_item")
