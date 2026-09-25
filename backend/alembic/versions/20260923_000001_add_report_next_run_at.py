"""add report.next_run_at

Revision ID: 20260923_000001
Revises: 20260920_000002
Create Date: 2026-09-23 00:00:01.000000

定时报告落地：
- `report.next_run_at` 记录该条定时报告的下次生成时刻（UTC，timestamptz）。
  后台调度器按此列轮询到期记录，重新生成后推进到下一个周期。
- 历史数据里 scheduled=True 的行补一个 next_run_at（生成时间 + 周期），
  否则它们永远等不到第一次触发；scheduled=False 的行保持 NULL。
"""

import sqlalchemy as sa
from alembic import op

revision = "20260923_000001"
down_revision = "20260920_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report",
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 已存在的定时配置补上下次生成时刻：以最后一次生成时间为基准往后推一个周期
    op.execute(
        """
        UPDATE report
        SET next_run_at = generated_at + (GREATEST(COALESCE(interval_days, 1), 1) * INTERVAL '1 day')
        WHERE scheduled IS TRUE
          AND next_run_at IS NULL
        """
    )
    # 调度器按 (scheduled, next_run_at) 扫描到期记录，建部分索引避免全表扫
    op.create_index(
        "ix_report_due_schedule",
        "report",
        ["next_run_at"],
        unique=False,
        postgresql_where=sa.text("scheduled IS TRUE AND next_run_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_report_due_schedule", table_name="report")
    op.drop_column("report", "next_run_at")
