"""add_rules_audit_fields_to_scripts

Revision ID: 2b6b6a9e5a21
Revises: 8db54f3c3438
Create Date: 2025-12-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "2b6b6a9e5a21"
down_revision: Union[str, None] = "8db54f3c3438"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""

    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("scripts")}

    if "rules_audit_status" not in existing_cols:
        op.add_column("scripts", sa.Column("rules_audit_status", sa.String(length=20), nullable=True))
    if "rules_audit_changed" not in existing_cols:
        op.add_column("scripts", sa.Column("rules_audit_changed", sa.Boolean(), nullable=True))
    if "rules_audit_model" not in existing_cols:
        op.add_column("scripts", sa.Column("rules_audit_model", sa.String(length=50), nullable=True))
    if "rules_audit_checked_at" not in existing_cols:
        op.add_column("scripts", sa.Column("rules_audit_checked_at", sa.DateTime(timezone=True), nullable=True))
    if "rules_audit_error" not in existing_cols:
        op.add_column("scripts", sa.Column("rules_audit_error", sa.Text(), nullable=True))

    existing_indexes = {i["name"] for i in inspector.get_indexes("scripts")}
    if "ix_scripts_rules_audit_status" not in existing_indexes:
        op.create_index("ix_scripts_rules_audit_status", "scripts", ["rules_audit_status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("scripts")}

    # 幂等删除索引
    op.execute("DROP INDEX IF EXISTS ix_scripts_rules_audit_status")

    if "rules_audit_error" in existing_cols:
        op.drop_column("scripts", "rules_audit_error")
    if "rules_audit_checked_at" in existing_cols:
        op.drop_column("scripts", "rules_audit_checked_at")
    if "rules_audit_model" in existing_cols:
        op.drop_column("scripts", "rules_audit_model")
    if "rules_audit_changed" in existing_cols:
        op.drop_column("scripts", "rules_audit_changed")
    if "rules_audit_status" in existing_cols:
        op.drop_column("scripts", "rules_audit_status")


