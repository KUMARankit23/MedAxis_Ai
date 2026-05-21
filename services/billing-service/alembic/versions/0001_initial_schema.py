"""Initial schema — prescriptions, invoices, invoice_items tables.

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
    op.execute("CREATE TYPE invoicestatus AS ENUM ('DRAFT', 'CONFIRMED', 'CANCELLED', 'REFUNDED')")
    op.execute("CREATE TYPE paymentmethod AS ENUM ('CASH', 'CARD', 'INSURANCE', 'UPI')")

    op.create_table(
        "prescriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_name", sa.String(200), nullable=False),
        sa.Column("patient_phone", sa.String(20), nullable=True),
        sa.Column("doctor_name", sa.String(200), nullable=False),
        sa.Column("doctor_license", sa.String(100), nullable=True),
        sa.Column("prescription_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("outlet_id", sa.String(50), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("outlet_id", sa.String(50), nullable=False),
        sa.Column(
            "prescription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id"),
            nullable=True,
        ),
        sa.Column("patient_name", sa.String(200), nullable=True),
        sa.Column("pharmacist_id", sa.String(200), nullable=False),
        sa.Column("subtotal", sa.Float(), nullable=True, server_default="0"),
        sa.Column("discount", sa.Float(), nullable=True, server_default="0"),
        sa.Column("tax", sa.Float(), nullable=True, server_default="0"),
        sa.Column("total", sa.Float(), nullable=True, server_default="0"),
        sa.Column(
            "payment_method",
            sa.Enum("CASH", "CARD", "INSURANCE", "UPI", name="paymentmethod"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "CONFIRMED", "CANCELLED", "REFUNDED", name="invoicestatus"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_outlet_id", "invoices", ["outlet_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_created_at", "invoices", ["created_at"])

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id"),
            nullable=False,
        ),
        sa.Column("medicine_id", sa.String(200), nullable=False),
        sa.Column("medicine_name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("discount_pct", sa.Float(), nullable=True, server_default="0"),
        sa.Column("gst_rate", sa.Float(), nullable=True, server_default="0.05"),
        sa.Column("line_total", sa.Float(), nullable=False),
        sa.Column("is_prescription_item", sa.Boolean(), nullable=True, server_default="false"),
    )


def downgrade() -> None:
    op.drop_table("invoice_items")
    op.drop_index("ix_invoices_created_at", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_outlet_id", table_name="invoices")
    op.drop_index("ix_invoices_invoice_number", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("prescriptions")
    op.execute("DROP TYPE paymentmethod")
    op.execute("DROP TYPE invoicestatus")
