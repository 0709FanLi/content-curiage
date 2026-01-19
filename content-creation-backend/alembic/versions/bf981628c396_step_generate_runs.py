"""step_generate_runs

Revision ID: bf981628c396
Revises: 2f1a3b4c5d6e
Create Date: 2026-01-16 18:28:30.219308

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'bf981628c396'
down_revision: Union[str, None] = '2f1a3b4c5d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    说明：本地开发库可能已通过 create_all 生成过表；这里保持幂等。
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "step_runs" not in existing_tables:
        op.create_table(
            "step_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=True),
            sa.Column("inspiration", sa.Text(), nullable=False, server_default=""),
            sa.Column("total_duration_sec", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("segment_duration_sec", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("aspect_ratio", sa.String(length=20), nullable=True),
            sa.Column("enable_storyboard", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("enable_seedream_group", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("video_mode", sa.String(length=20), nullable=False, server_default="auto"),
            sa.Column("decision_model_primary", sa.String(length=50), nullable=False, server_default="deepseek-chat"),
            sa.Column("decision_model_fallback", sa.String(length=50), nullable=False, server_default="gemini-3-pro"),
            sa.Column("decision_thinking_level", sa.String(length=20), nullable=False, server_default="low"),
            sa.Column(
                "status",
                sa.Enum("pending", "running", "completed", "failed", "cancelled", name="steprunstatus"),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("final_video_url", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_step_runs_id", "step_runs", ["id"])
        op.create_index("ix_step_runs_user_id", "step_runs", ["user_id"])
        op.create_index("ix_step_runs_project_id", "step_runs", ["project_id"])
        op.create_index("ix_step_runs_script_id", "step_runs", ["script_id"])

    # 增量兼容：历史库已存在 step_runs 时，补齐新列（幂等）
    else:
        cols = {c.get("name") for c in inspector.get_columns("step_runs")}
        if "enable_storyboard" not in cols:
            op.add_column("step_runs", sa.Column("enable_storyboard", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "enable_seedream_group" not in cols:
            op.add_column("step_runs", sa.Column("enable_seedream_group", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "video_mode" not in cols:
            op.add_column("step_runs", sa.Column("video_mode", sa.String(length=20), nullable=False, server_default="auto"))

    if "step_segments" not in existing_tables:
        op.create_table(
            "step_segments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("step_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("segment_index", sa.Integer(), nullable=False),
            sa.Column("segment_id", sa.String(length=50), nullable=False, server_default="segment_0"),
            sa.Column("start_ms", sa.Integer(), nullable=True),
            sa.Column("end_ms", sa.Integer(), nullable=True),
            sa.Column("narration", sa.Text(), nullable=True),
            sa.Column("video_desc", sa.Text(), nullable=True),
            sa.Column("voice_desc", sa.Text(), nullable=True),
            sa.Column("audio_url", sa.String(length=500), nullable=True),
            sa.Column("audio_duration_sec", sa.Float(), nullable=True),
            sa.Column("video_segment_id", sa.Integer(), sa.ForeignKey("video_segments.id"), nullable=True),
            sa.Column("video_url", sa.String(length=500), nullable=True),
            sa.Column("merged_video_url", sa.String(length=500), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_step_segments_id", "step_segments", ["id"])
        op.create_index("ix_step_segments_run_id", "step_segments", ["run_id"])
        op.create_index("ix_step_segments_segment_index", "step_segments", ["segment_index"])
        op.create_index("ix_step_segments_video_segment_id", "step_segments", ["video_segment_id"])

    if "step_run_events" not in existing_tables:
        op.create_table(
            "step_run_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("step_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("level", sa.String(length=20), nullable=False, server_default="info"),
            sa.Column("event_type", sa.String(length=50), nullable=False, server_default="log"),
            sa.Column("message", sa.Text(), nullable=False, server_default=""),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_step_run_events_id", "step_run_events", ["id"])
        op.create_index("ix_step_run_events_run_id", "step_run_events", ["run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "step_run_events" in existing_tables:
        op.drop_index("ix_step_run_events_run_id", table_name="step_run_events")
        op.drop_index("ix_step_run_events_id", table_name="step_run_events")
        op.drop_table("step_run_events")

    if "step_segments" in existing_tables:
        op.drop_index("ix_step_segments_video_segment_id", table_name="step_segments")
        op.drop_index("ix_step_segments_segment_index", table_name="step_segments")
        op.drop_index("ix_step_segments_run_id", table_name="step_segments")
        op.drop_index("ix_step_segments_id", table_name="step_segments")
        op.drop_table("step_segments")

    if "step_runs" in existing_tables:
        # 若为增量升级场景：优先尝试 drop 新增列（表存在但不想 drop 整表时的兼容）
        try:
            cols = {c.get("name") for c in inspector.get_columns("step_runs")}
            for col in ("video_mode", "enable_seedream_group", "enable_storyboard"):
                if col in cols:
                    op.drop_column("step_runs", col)
        except Exception:
            pass
        op.drop_index("ix_step_runs_script_id", table_name="step_runs")
        op.drop_index("ix_step_runs_project_id", table_name="step_runs")
        op.drop_index("ix_step_runs_user_id", table_name="step_runs")
        op.drop_index("ix_step_runs_id", table_name="step_runs")
        op.drop_table("step_runs")

    # Enum 类型清理（SQLite 下通常会忽略，但在 PostgreSQL 下需要显式 drop）
    try:
        op.execute("DROP TYPE steprunstatus")
    except Exception:
        pass

