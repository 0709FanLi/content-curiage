"""step_runs add storyboard fields

Revision ID: c8f2a1d3e2aa
Revises: bf981628c396
Create Date: 2026-01-18

说明：
- 由于 bf981628c396 迁移在部分环境中已被标记为已执行（version_table=HEAD），即使我们后续修改了该迁移文件，
  Alembic 也不会重新执行它的 upgrade()，从而导致本地 SQLite 的 step_runs 缺少新列。
- 本迁移作为“补丁迁移”，专门为已存在的 step_runs 表补齐列，避免丢数据。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c8f2a1d3e2aa"
down_revision: Union[str, None] = "bf981628c396"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "step_runs" not in existing_tables:
        return

    cols = {c.get("name") for c in inspector.get_columns("step_runs")}

    if "enable_storyboard" not in cols:
        op.add_column(
            "step_runs",
            sa.Column("enable_storyboard", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "enable_seedream_group" not in cols:
        op.add_column(
            "step_runs",
            sa.Column("enable_seedream_group", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "video_mode" not in cols:
        op.add_column(
            "step_runs",
            sa.Column("video_mode", sa.String(length=20), nullable=False, server_default="auto"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "step_runs" not in existing_tables:
        return

    cols = {c.get("name") for c in inspector.get_columns("step_runs")}
    # SQLite 支持 drop_column 的版本差异较大；这里尽力而为，不强制失败
    for col in ("video_mode", "enable_seedream_group", "enable_storyboard"):
        try:
            if col in cols:
                op.drop_column("step_runs", col)
        except Exception:
            pass

