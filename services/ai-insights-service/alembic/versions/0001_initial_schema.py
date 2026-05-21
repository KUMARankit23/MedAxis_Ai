"""Initial schema — forecast_results and anomaly_logs tables.

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
    op.create_table(
        "forecast_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("medicine_id", sa.String(200), nullable=False),
        sa.Column("medicine_name", sa.String(200), nullable=True),
        sa.Column("outlet_id", sa.String(50), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("predicted_demand", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("triggered_replenishment", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_forecast_results_medicine_id", "forecast_results", ["medicine_id"])

    op.create_table(
        "anomaly_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("anomaly_type", sa.String(100), nullable=False),
        sa.Column("medicine_id", sa.String(200), nullable=True),
        sa.Column("outlet_id", sa.String(50), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("detected_value", sa.Float(), nullable=True),
        sa.Column("expected_range", sa.String(100), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_anomaly_logs_medicine_id", "anomaly_logs", ["medicine_id"])
    op.create_index("ix_anomaly_logs_is_resolved", "anomaly_logs", ["is_resolved"])
    op.create_index("ix_anomaly_logs_detected_at", "anomaly_logs", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_anomaly_logs_detected_at", table_name="anomaly_logs")
    op.drop_index("ix_anomaly_logs_is_resolved", table_name="anomaly_logs")
    op.drop_index("ix_anomaly_logs_medicine_id", table_name="anomaly_logs")
    op.drop_table("anomaly_logs")
    op.drop_index("ix_forecast_results_medicine_id", table_name="forecast_results")
    op.drop_table("forecast_results")
