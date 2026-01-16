"""add cancelled_at to scripts

Revision ID: 2f1a3b4c5d6e
Revises: dbe16dd78632
Create Date: 2026-01-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "2f1a3b4c5d6e"
down_revision = "dbe16dd78632"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("scripts")}
    if "cancelled_at" in existing:
        return

    op.add_column(
        "scripts",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("scripts")}
    if "cancelled_at" not in existing:
        return

    op.drop_column("scripts", "cancelled_at")


