"""Initial schema — replenishment_orders and po_counters tables.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE orderstatus AS ENUM "
        "('SUGGESTED', 'APPROVED', 'ORDERED', 'RECEIVED', 'CANCELLED')"
    )

    op.create_table(
        "replenishment_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("po_number", sa.String(50), nullable=True),
        sa.Column("medicine_id", sa.String(200), nullable=False),
        sa.Column("medicine_name", sa.String(200), nullable=True),
        sa.Column("outlet_id", sa.String(50), nullable=False),
        sa.Column("suggested_quantity", sa.Integer(), nullable=False),
        sa.Column("approved_quantity", sa.Integer(), nullable=True),
        sa.Column("trigger_reason", sa.String(100), nullable=False),
        sa.Column("current_stock", sa.Integer(), nullable=True),
        sa.Column("reorder_level", sa.Integer(), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "SUGGESTED", "APPROVED", "ORDERED", "RECEIVED", "CANCELLED",
                name="orderstatus",
            ),
            nullable=True,
        ),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_replenishment_orders_po_number", "replenishment_orders", ["po_number"])
    op.create_index("ix_replenishment_orders_status", "replenishment_orders", ["status"])
    op.create_index("ix_replenishment_orders_created_at", "replenishment_orders", ["created_at"])

    op.create_table(
        "po_counters",
        sa.Column("date_key", sa.String(8), primary_key=True),
        sa.Column("last_seq", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("po_counters")
    op.drop_index("ix_replenishment_orders_created_at", table_name="replenishment_orders")
    op.drop_index("ix_replenishment_orders_status", table_name="replenishment_orders")
    op.drop_index("ix_replenishment_orders_po_number", table_name="replenishment_orders")
    op.drop_table("replenishment_orders")
    op.execute("DROP TYPE orderstatus")
