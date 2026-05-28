"""add unique constraint on ports.locode

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-28 00:01:00.000000

locode is a global UN/LOCODE port identifier and must be unique for
ON CONFLICT (locode) upserts in the seed script and collectors.
"""
from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_ports_locode_unique", "ports", ["locode"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ports_locode_unique", table_name="ports")
