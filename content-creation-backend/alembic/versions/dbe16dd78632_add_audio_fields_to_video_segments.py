"""add_audio_fields_to_video_segments

Revision ID: dbe16dd78632
Revises: 2b6b6a9e5a21
Create Date: 2026-01-04 11:09:18.383412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dbe16dd78632'
down_revision: Union[str, None] = '2b6b6a9e5a21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    audio_status_enum = sa.Enum(
        'PENDING',
        'GENERATING',
        'COMPLETED',
        'FAILED',
        name='audiostatus',
    )
    bind = op.get_bind()
    audio_status_enum.create(bind, checkfirst=True)

    op.add_column(
        'video_segments',
        sa.Column('audio_url', sa.String(length=500), nullable=True),
    )
    op.add_column(
        'video_segments',
        sa.Column(
            'audio_status',
            audio_status_enum,
            nullable=False,
            server_default='PENDING',
        ),
    )
    op.add_column(
        'video_segments',
        sa.Column('audio_error_message', sa.Text(), nullable=True),
    )
    op.add_column(
        'video_segments',
        sa.Column('audio_duration_sec', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('video_segments', 'audio_duration_sec')
    op.drop_column('video_segments', 'audio_error_message')
    op.drop_column('video_segments', 'audio_status')
    op.drop_column('video_segments', 'audio_url')

    bind = op.get_bind()
    audio_status_enum = sa.Enum(
        'PENDING',
        'GENERATING',
        'COMPLETED',
        'FAILED',
        name='audiostatus',
    )
    audio_status_enum.drop(bind, checkfirst=True)

