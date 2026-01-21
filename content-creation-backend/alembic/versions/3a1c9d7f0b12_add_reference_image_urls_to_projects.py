"""add reference_image_urls to projects

Revision ID: 3a1c9d7f0b12
Revises: 2f1a3b4c5d6e
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "3a1c9d7f0b12"
down_revision = "2f1a3b4c5d6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("projects")}
    if "reference_image_urls" in existing:
        return

    op.add_column("projects", sa.Column("reference_image_urls", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("projects")}
    if "reference_image_urls" not in existing:
        return
    op.drop_column("projects", "reference_image_urls")

