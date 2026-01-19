"""add_medeo_projects_table

Revision ID: f3b1c2d3e4f5
Revises: 2f1a3b4c5d6e, 8db54f3c3438
Create Date: 2026-01-19 14:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = ("2f1a3b4c5d6e", "8db54f3c3438")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medeo_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("medeo_project_id", sa.String(length=64), nullable=True),
        sa.Column("video_draft_id", sa.String(length=64), nullable=True),
        sa.Column("chat_session_id", sa.String(length=64), nullable=True),
        sa.Column("video_draft_op_record_id", sa.String(length=64), nullable=True),
        sa.Column("last_task_status", sa.String(length=32), nullable=True),
        sa.Column("render_status", sa.String(length=32), nullable=True),
        sa.Column("render_url", sa.String(length=512), nullable=True),
        sa.Column("render_metadata", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_medeo_projects_project_id", "medeo_projects", ["project_id"], unique=True)
    op.create_index("ix_medeo_projects_chat_session_id", "medeo_projects", ["chat_session_id"], unique=False)
    op.create_index("ix_medeo_projects_video_draft_id", "medeo_projects", ["video_draft_id"], unique=False)
    op.create_index("ix_medeo_projects_medeo_project_id", "medeo_projects", ["medeo_project_id"], unique=False)
    op.create_index("ix_medeo_projects_video_draft_op_record_id", "medeo_projects", ["video_draft_op_record_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_medeo_projects_video_draft_op_record_id", table_name="medeo_projects")
    op.drop_index("ix_medeo_projects_medeo_project_id", table_name="medeo_projects")
    op.drop_index("ix_medeo_projects_video_draft_id", table_name="medeo_projects")
    op.drop_index("ix_medeo_projects_chat_session_id", table_name="medeo_projects")
    op.drop_index("ix_medeo_projects_project_id", table_name="medeo_projects")
    op.drop_table("medeo_projects")

