"""add_first_script_generated_at_to_projects

Revision ID: c837d165e2a9
Revises: 0c20fbb5342b
Create Date: 2025-11-21 14:44:40.937666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c837d165e2a9'
down_revision: Union[str, None] = '0c20fbb5342b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    说明：部分生产环境已手工添加过字段；这里保持幂等，避免 DuplicateColumn。
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('projects')}
    if 'first_script_generated_at' in existing:
        return

    op.add_column(
        'projects',
        sa.Column('first_script_generated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('projects')}
    if 'first_script_generated_at' not in existing:
        return

    op.drop_column('projects', 'first_script_generated_at')

