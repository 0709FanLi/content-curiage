"""add_timeline_asset_track_clip_tables

Revision ID: 8db54f3c3438
Revises: 9552e96d3987
Create Date: 2025-12-22 23:17:26.357009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8db54f3c3438'
down_revision: Union[str, None] = '9552e96d3987'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    说明：部分生产环境可能已经提前创建了这些表/枚举类型。
    这里做幂等处理：表存在则跳过创建；枚举存在则不重复创建。
    """

    bind = op.get_bind()
    inspector = inspect(bind)

    def enum_exists(name: str) -> bool:
        return bool(
            bind.execute(
                text("SELECT 1 FROM pg_type WHERE typname = :n LIMIT 1"),
                {'n': name},
            ).scalar(),
        )

    asset_type_enum = postgresql.ENUM(
        'IMAGE', 'VIDEO', 'AUDIO', 'DOCUMENT',
        name='assettype',
        create_type=not enum_exists('assettype'),
    )
    asset_source_enum = postgresql.ENUM(
        'GENERATED', 'UPLOADED', 'LIBRARY',
        name='assetsource',
        create_type=not enum_exists('assetsource'),
    )
    track_type_enum = postgresql.ENUM(
        'VIDEO', 'SPEECH', 'BGM', 'CAPTION',
        name='tracktype',
        create_type=not enum_exists('tracktype'),
    )

    existing_tables = set(inspector.get_table_names())

    if 'assets' not in existing_tables:
        op.create_table(
            'assets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=500), nullable=True),
            sa.Column('type', asset_type_enum, nullable=False),
            sa.Column('source', asset_source_enum, nullable=False),
            sa.Column('url', sa.Text(), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=True),
            sa.Column('mime_type', sa.String(length=100), nullable=True),
            sa.Column('duration_ms', sa.Integer(), nullable=True),
            sa.Column('width', sa.Integer(), nullable=True),
            sa.Column('height', sa.Integer(), nullable=True),
            sa.Column('extra_data', sa.JSON(), nullable=True),
            sa.Column('parent_asset_id', sa.Integer(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['parent_asset_id'], ['assets.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_assets_id'), 'assets', ['id'], unique=False)
        op.create_index(op.f('ix_assets_project_id'), 'assets', ['project_id'], unique=False)

    if 'timelines' not in existing_tables:
        op.create_table(
            'timelines',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('duration_ms', sa.Integer(), nullable=False),
            sa.Column('aspect_ratio', sa.String(length=20), nullable=False),
            sa.Column('fps', sa.Integer(), nullable=False),
            sa.Column('playhead_ms', sa.Integer(), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_timelines_id'), 'timelines', ['id'], unique=False)
        op.create_index(op.f('ix_timelines_project_id'), 'timelines', ['project_id'], unique=True)

    if 'tracks' not in existing_tables:
        op.create_table(
            'tracks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('timeline_id', sa.Integer(), nullable=False),
            sa.Column('type', track_type_enum, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=True),
            sa.Column('is_muted', sa.Boolean(), nullable=False),
            sa.Column('is_locked', sa.Boolean(), nullable=False),
            sa.Column('volume', sa.Float(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['timeline_id'], ['timelines.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_tracks_id'), 'tracks', ['id'], unique=False)
        op.create_index(op.f('ix_tracks_timeline_id'), 'tracks', ['timeline_id'], unique=False)

    if 'clips' not in existing_tables:
        op.create_table(
            'clips',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('track_id', sa.Integer(), nullable=False),
            sa.Column('asset_id', sa.Integer(), nullable=True),
            sa.Column('start_ms', sa.Integer(), nullable=False),
            sa.Column('end_ms', sa.Integer(), nullable=False),
            sa.Column('asset_start_ms', sa.Integer(), nullable=False),
            sa.Column('asset_end_ms', sa.Integer(), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('properties', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_clips_asset_id'), 'clips', ['asset_id'], unique=False)
        op.create_index(op.f('ix_clips_id'), 'clips', ['id'], unique=False)
        op.create_index(op.f('ix_clips_track_id'), 'clips', ['track_id'], unique=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_clips_track_id'), table_name='clips')
    op.drop_index(op.f('ix_clips_id'), table_name='clips')
    op.drop_index(op.f('ix_clips_asset_id'), table_name='clips')
    op.drop_table('clips')
    op.drop_index(op.f('ix_tracks_timeline_id'), table_name='tracks')
    op.drop_index(op.f('ix_tracks_id'), table_name='tracks')
    op.drop_table('tracks')
    op.drop_index(op.f('ix_timelines_project_id'), table_name='timelines')
    op.drop_index(op.f('ix_timelines_id'), table_name='timelines')
    op.drop_table('timelines')
    op.drop_index(op.f('ix_assets_project_id'), table_name='assets')
    op.drop_index(op.f('ix_assets_id'), table_name='assets')
    op.drop_table('assets')
    # ### end Alembic commands ###

