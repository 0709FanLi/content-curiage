"""Add generation_mode to projects table

Revision ID: 9552e96d3987
Revises: 6898a7d06e8a
Create Date: 2025-12-04 10:08:46.872395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '9552e96d3987'
down_revision: Union[str, None] = '6898a7d06e8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    说明：部分生产环境已手工添加过字段；这里保持幂等，避免 DuplicateColumn。
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('projects')}

    # 已存在则只做数据补齐
    if 'generation_mode' in existing:
        op.execute("UPDATE projects SET generation_mode = 'step_by_step' WHERE generation_mode IS NULL")
        return

    # 先添加可为空的列
    op.add_column('projects', sa.Column('generation_mode', sa.String(length=20), nullable=True))
    # 更新现有数据，设置默认值为 'step_by_step'
    op.execute("UPDATE projects SET generation_mode = 'step_by_step' WHERE generation_mode IS NULL")
    # 修改列为 NOT NULL（SQLite 不支持直接修改，所以保持为 nullable=True）


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c['name'] for c in inspector.get_columns('projects')}
    if 'generation_mode' not in existing:
        return

    op.drop_column('projects', 'generation_mode')

