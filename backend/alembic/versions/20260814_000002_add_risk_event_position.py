"""add fault_position_x/y to risk_event (flightdeck heatmap coords)

Revision ID: 20260814_000002
Revises: 20260814_000001
Create Date: 2026-08-14 00:00:02.000000

需求 V3.0 §7.4.1（航母甲板热点图）：
- 航母甲板作业场景生成 RiskEvent 时，额外存储故障点坐标
  fault_position_x / fault_position_y（像素，基准底图宽度 1000px）；
- 非航母场景的风险事件这两个字段留空（NULL），前端不渲染红点。

实现：risk_event 增加两个可空 Numeric 列。
"""
import sqlalchemy as sa
from alembic import op

revision = "20260814_000002"
down_revision = "20260814_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "risk_event",
        sa.Column("fault_position_x", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "risk_event",
        sa.Column("fault_position_y", sa.Numeric(8, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("risk_event", "fault_position_y")
    op.drop_column("risk_event", "fault_position_x")
