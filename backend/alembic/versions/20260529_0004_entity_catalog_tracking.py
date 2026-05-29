"""add portid/chokepointid business keys and is_tracked flags

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-29 00:04:00.000000

PortWatch data is keyed by an internal portid/chokepointid. These become the
unique business key (API id + metric entity_id) while the int surrogate id is
kept so existing FKs are untouched. is_tracked drives which entities get
metrics fetched, news, and scoring. The known 14 ports + 8 chokepoints are
backfilled with their portids and marked tracked.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# Known seed entities -> PortWatch portid (verified against the master DB).
_PORT_PORTID = {
    "AEJEA": "port744", "BEANR": "port57", "CNGZH": "port425",
    "CNNGB": "port824", "CNSHA": "port1188", "CNSZX": "port1189",
    "CNTAO": "port1069", "CNTXG": "port1297", "HKHKG": "port474",
    "KRPUS": "port1065", "MYPKG": "port960", "NLRTM": "port1114",
    "SGSIN": "port1201", "USLAX": "port664",
}
_CHOKEPOINT_PORTID = {
    "Suez Canal": "chokepoint1", "Panama Canal": "chokepoint2",
    "Bab-el-Mandeb": "chokepoint4", "Strait of Malacca": "chokepoint5",
    "Strait of Hormuz": "chokepoint6", "Strait of Gibraltar": "chokepoint8",
    "Strait of Dover": "chokepoint9", "Lombok Strait": "chokepoint15",
}


def upgrade() -> None:
    # 1. Add columns nullable so we can backfill before enforcing NOT NULL.
    op.add_column("ports", sa.Column("portid", sa.String(32), nullable=True))
    op.add_column(
        "ports",
        sa.Column(
            "is_tracked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "chokepoints", sa.Column("chokepointid", sa.String(32), nullable=True)
    )
    op.add_column(
        "chokepoints",
        sa.Column(
            "is_tracked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )

    conn = op.get_bind()

    # 2. Backfill known entities by locode / name, mark tracked.
    for locode, portid in _PORT_PORTID.items():
        conn.execute(
            sa.text(
                "UPDATE ports SET portid=:pid, is_tracked=true WHERE locode=:loc"
            ),
            {"pid": portid, "loc": locode},
        )
    for name, cpid in _CHOKEPOINT_PORTID.items():
        conn.execute(
            sa.text(
                "UPDATE chokepoints SET chokepointid=:cid, is_tracked=true "
                "WHERE name=:nm"
            ),
            {"cid": cpid, "nm": name},
        )

    # 3. Any rows still without a business key (unexpected in practice) get a
    #    deterministic legacy id so the NOT NULL + UNIQUE constraints hold.
    conn.execute(
        sa.text(
            "UPDATE ports SET portid='legacy-port-' || id WHERE portid IS NULL"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE chokepoints SET chokepointid='legacy-cp-' || id "
            "WHERE chokepointid IS NULL"
        )
    )

    # 4. Enforce NOT NULL + UNIQUE.
    op.alter_column("ports", "portid", existing_type=sa.String(32), nullable=False)
    op.alter_column(
        "chokepoints", "chokepointid", existing_type=sa.String(32), nullable=False
    )
    op.create_index("ix_ports_portid", "ports", ["portid"], unique=True)
    op.create_index(
        "ix_chokepoints_chokepointid", "chokepoints", ["chokepointid"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_chokepoints_chokepointid", table_name="chokepoints")
    op.drop_index("ix_ports_portid", table_name="ports")
    op.drop_column("chokepoints", "is_tracked")
    op.drop_column("chokepoints", "chokepointid")
    op.drop_column("ports", "is_tracked")
    op.drop_column("ports", "portid")
