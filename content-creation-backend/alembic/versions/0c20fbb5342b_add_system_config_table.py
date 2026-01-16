"""add_system_config_table

Revision ID: 0c20fbb5342b
Revises: 673585e4ae94
Create Date: 2025-11-20 09:53:17.942248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '0c20fbb5342b'
down_revision: Union[str, None] = '673585e4ae94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    说明：部分生产环境已手工创建过 `system_configs` 表。
    这里做幂等处理：若表已存在则跳过，避免 DuplicateTable 中断部署。
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'system_configs' in inspector.get_table_names():
        return

    # 创建系统配置表
    op.create_table(
        'system_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('config_key', sa.String(length=100), nullable=False, comment='配置键'),
        sa.Column('config_value', sa.Text(), nullable=False, comment='配置值'),
        sa.Column('description', sa.String(length=500), nullable=True, comment='配置描述'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_configs_id'), 'system_configs', ['id'], unique=False)
    op.create_index(op.f('ix_system_configs_config_key'), 'system_configs', ['config_key'], unique=True)


def downgrade() -> None:
    """Downgrade schema.

    生产环境不建议执行 downgrade；这里保持幂等，避免对象不存在时报错。
    """

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'system_configs' not in inspector.get_table_names():
        return

    # 删除索引和表（使用 IF EXISTS 保持幂等）
    op.execute('DROP INDEX IF EXISTS ix_system_configs_config_key')
    op.execute('DROP INDEX IF EXISTS ix_system_configs_id')
    op.drop_table('system_configs')

