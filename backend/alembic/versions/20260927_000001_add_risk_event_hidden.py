"""add risk_event.hidden_at / hidden_by_user_id

Revision ID: 20260927_000001
Revises: 20260923_000001
Create Date: 2026-09-27 00:00:01.000000

风险事件「隐藏」（软删除）：

- 需求 5.2 访问控制第 4 条明确「历史风险事件不得被无痕删除或自动改写」，
  所以 `RiskEventService.delete` 一直是直接返回 400。列表需要一个「把不要的行收起来」
  的动作，于是用可见性开关而不是真删：`hidden_at` 非空 = 已隐藏。
- 数据、处置记录（handling_record）、统计口径都不受影响 —— 隐藏只改变列表是否显示。
- `hidden_by_user_id` 记录是谁隐藏的，便于追溯。
- 列表默认过滤 `hidden_at IS NULL`，勾选「显示已隐藏」时不过滤；建部分索引避免全表扫。
"""

import sqlalchemy as sa
from alembic import op

revision = "20260927_000001"
down_revision = "20260923_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "risk_event",
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "risk_event",
        sa.Column("hidden_by_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "risk_event_hidden_by_user_id_fkey",
        "risk_event",
        "app_user",
        ["hidden_by_user_id"],
        ["id"],
    )
    # 列表默认只查未隐藏的、按 occurred_at desc 排；部分索引正好覆盖这个查询
    op.create_index(
        "ix_risk_event_visible",
        "risk_event",
        ["occurred_at"],
        unique=False,
        postgresql_where=sa.text("hidden_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_risk_event_visible", table_name="risk_event")
    op.drop_constraint(
        "risk_event_hidden_by_user_id_fkey", "risk_event", type_="foreignkey"
    )
    op.drop_column("risk_event", "hidden_by_user_id")
    op.drop_column("risk_event", "hidden_at")
