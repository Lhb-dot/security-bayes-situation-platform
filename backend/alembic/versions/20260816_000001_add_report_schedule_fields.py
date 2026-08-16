"""add scenario_id / format / scheduled / interval_days to report

Revision ID: 20260816_000001
Revises: 20260814_000004
Create Date: 2026-08-16 00:00:01.000000

报告支持场景隔离与定时生成：
- scenario_id：报告归属场景（FK → scenario.id），用于三级角色场景隔离
- format：报告格式（markdown/html/pdf）
- scheduled：是否定时生成
- interval_days：定时生成周期（天）
"""
import sqlalchemy as sa
from alembic import op

revision = "20260816_000001"
down_revision = "20260814_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report",
        sa.Column("scenario_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_scenario",
        "report",
        "scenario",
        ["scenario_id"],
        ["id"],
    )
    op.add_column(
        "report",
        sa.Column("format", sa.String(16), nullable=False, server_default="markdown"),
    )
    op.add_column(
        "report",
        sa.Column("scheduled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "report",
        sa.Column("interval_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_constraint("fk_report_scenario", "report", type_="foreignkey")
    op.drop_column("report", "interval_days")
    op.drop_column("report", "scheduled")
    op.drop_column("report", "format")
    op.drop_column("report", "scenario_id")
