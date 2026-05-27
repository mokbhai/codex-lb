"""add account custom routing fields

Revision ID: 20260527_000000_add_account_custom_routing_fields
Revises: 20260525_000000_add_usage_raw_window_latest_index
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260527_000000_add_account_custom_routing_fields"
down_revision = "20260525_000000_add_usage_raw_window_latest_index"
branch_labels = None
depends_on = None


def _columns(connection: Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(connection)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "accounts")
    if not columns:
        return
    with op.batch_alter_table("accounts") as batch_op:
        if "custom_api_key_encrypted" not in columns:
            batch_op.add_column(sa.Column("custom_api_key_encrypted", sa.LargeBinary(), nullable=True))
        if "custom_base_url" not in columns:
            batch_op.add_column(sa.Column("custom_base_url", sa.String(), nullable=True))
        if "custom_model_mapping_json" not in columns:
            batch_op.add_column(sa.Column("custom_model_mapping_json", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "accounts")
    if not columns:
        return
    with op.batch_alter_table("accounts") as batch_op:
        if "custom_model_mapping_json" in columns:
            batch_op.drop_column("custom_model_mapping_json")
        if "custom_base_url" in columns:
            batch_op.drop_column("custom_base_url")
        if "custom_api_key_encrypted" in columns:
            batch_op.drop_column("custom_api_key_encrypted")
