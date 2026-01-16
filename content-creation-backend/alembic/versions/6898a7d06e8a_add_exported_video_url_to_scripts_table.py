"""Add exported_video_url to scripts table

Revision ID: 6898a7d06e8a
Revises: c837d165e2a9
Create Date: 2025-12-03 23:25:31.209272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '6898a7d06e8a'
down_revision: Union[str, None] = 'c837d165e2a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    说明：部分生产环境已手工添加过字段；这里保持幂等，避免 DuplicateColumn。
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('scripts')}
    if 'exported_video_url' in existing:
        return

    op.add_column(
        'scripts',
        sa.Column('exported_video_url', sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('scripts')}
    if 'exported_video_url' not in existing:
        return

    op.drop_column('scripts', 'exported_video_url')

