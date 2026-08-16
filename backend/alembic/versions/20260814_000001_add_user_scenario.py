"""add scenario_id to app_user (user-scenario binding)

Revision ID: 20260814_000001
Revises: 20260808_000001
Create Date: 2026-08-14 00:00:01.000000

需求 V3.0 §1.1.2 / §1.1.6 / §6.5.2：
- 普通用户的场景由账号绑定关系自动确定，无需手动选择；
- 普通用户登录后仅能看到自己被分配的场景；
- 普通用户的场景分配由管理员在创建或管理账号时指定。

实现：app_user 增加可空 scenario_id（FK → scenario.id）。
管理员不绑定场景（scenario_id = NULL，可见全部场景）；普通用户绑定一个场景。
"""
import sqlalchemy as sa
from alembic import op

revision = "20260814_000001"
down_revision = "20260808_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("scenario_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_app_user_scenario",
        "app_user",
        "scenario",
        ["scenario_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_app_user_scenario", "app_user", type_="foreignkey")
    op.drop_column("app_user", "scenario_id")
