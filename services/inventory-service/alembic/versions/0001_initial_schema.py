"""Initial schema — medicines, inventory_batches, stock_ledger tables.

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
        "CREATE TYPE medicinecategory AS ENUM ('OTC', 'PRESCRIPTION', 'CONTROLLED')"
    )

    op.create_table(
        "medicines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("generic_name", sa.String(200), nullable=True),
        sa.Column("manufacturer", sa.String(200), nullable=True),
        sa.Column(
            "category",
            sa.Enum("OTC", "PRESCRIPTION", "CONTROLLED", name="medicinecategory"),
            nullable=False,
        ),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("reorder_level", sa.Integer(), nullable=True),
        sa.Column("reorder_quantity", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_medicines_name", "medicines", ["name"])

    op.create_table(
        "inventory_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "medicine_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medicines.id"),
            nullable=False,
        ),
        sa.Column("batch_number", sa.String(100), nullable=False),
        sa.Column("outlet_id", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("purchase_price", sa.Float(), nullable=True),
        sa.Column("is_quarantined", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_batch_medicine_outlet", "inventory_batches", ["medicine_id", "outlet_id"])
    op.create_index("ix_batch_expiry", "inventory_batches", ["expiry_date"])

    op.create_table(
        "stock_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "medicine_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medicines.id"),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_batches.id"),
            nullable=True,
        ),
        sa.Column("outlet_id", sa.String(50), nullable=False),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column("quantity_change", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reference_id", sa.String(200), nullable=True),
        sa.Column("performed_by", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ledger_medicine_outlet", "stock_ledger", ["medicine_id", "outlet_id"])
    op.create_index("ix_ledger_timestamp", "stock_ledger", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_ledger_timestamp", table_name="stock_ledger")
    op.drop_index("ix_ledger_medicine_outlet", table_name="stock_ledger")
    op.drop_table("stock_ledger")
    op.drop_index("ix_batch_expiry", table_name="inventory_batches")
    op.drop_index("ix_batch_medicine_outlet", table_name="inventory_batches")
    op.drop_table("inventory_batches")
    op.drop_index("ix_medicines_name", table_name="medicines")
    op.drop_table("medicines")
    op.execute("DROP TYPE medicinecategory")
