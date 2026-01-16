"""update_video_segment_table_for_first_last_frame

Revision ID: 673585e4ae94
Revises: 094490142390
Create Date: 2025-11-13 10:44:16.591506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '673585e4ae94'
down_revision: Union[str, None] = '094490142390'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    说明：部分生产环境曾手工创建过 `videostatus` 枚举类型。
    该迁移在 create_table 时会隐式尝试创建同名枚举，导致 DuplicateObject。
    这里做幂等处理：若枚举已存在则跳过创建。
    """

    bind = op.get_bind()
    enum_exists = bool(
        bind.execute(
            text("SELECT 1 FROM pg_type WHERE typname = 'videostatus' LIMIT 1"),
        ).scalar(),
    )

    video_status_enum = postgresql.ENUM(
        'PENDING',
        'GENERATING',
        'COMPLETED',
        'FAILED',
        name='videostatus',
        create_type=not enum_exists,
    )

    # 由于表结构变化较大且表中无数据，直接删除并重新创建表
    inspector = inspect(bind)
    if 'video_segments' in inspector.get_table_names():
        op.drop_table('video_segments')
    
    op.create_table(
        'video_segments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('script_id', sa.Integer(), nullable=False),
        sa.Column('segment_index', sa.Integer(), nullable=False),
        sa.Column('first_frame_url', sa.String(length=500), nullable=True),
        sa.Column('last_frame_url', sa.String(length=500), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('video_url', sa.String(length=500), nullable=True),
        sa.Column('model', sa.String(length=50), nullable=True),
        sa.Column('aspect_ratio', sa.String(length=20), nullable=True),
        sa.Column('status', video_status_enum, nullable=False),
        sa.Column('duration', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('task_id', sa.String(length=200), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['script_id'], ['scripts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_segments_id'), 'video_segments', ['id'], unique=False)
    op.create_index(op.f('ix_video_segments_script_id'), 'video_segments', ['script_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    # 恢复原始表结构
    op.drop_index(op.f('ix_video_segments_script_id'), table_name='video_segments')
    op.drop_index(op.f('ix_video_segments_id'), table_name='video_segments')
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'video_segments' in inspector.get_table_names():
        op.drop_table('video_segments')
    
    # 降级时同样保持幂等：若 enum 已存在则不重复创建
    enum_exists = bool(
        bind.execute(
            text("SELECT 1 FROM pg_type WHERE typname = 'videostatus' LIMIT 1"),
        ).scalar(),
    )
    video_status_enum = postgresql.ENUM(
        'PENDING',
        'GENERATING',
        'COMPLETED',
        'FAILED',
        name='videostatus',
        create_type=not enum_exists,
    )

    op.create_table(
        'video_segments',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('keyframe_id', sa.INTEGER(), nullable=False),
        sa.Column('video_url', sa.VARCHAR(length=500), nullable=True),
        sa.Column('status', video_status_enum, nullable=False),
        sa.Column('duration', sa.FLOAT(), nullable=False),
        sa.Column('error_message', sa.TEXT(), nullable=True),
        sa.Column('created_at', sa.DATETIME(), nullable=False),
        sa.Column('updated_at', sa.DATETIME(), nullable=False),
        sa.ForeignKeyConstraint(['keyframe_id'], ['keyframes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_video_segments_keyframe_id', 'video_segments', ['keyframe_id'], unique=False)
    op.create_index('ix_video_segments_id', 'video_segments', ['id'], unique=False)

