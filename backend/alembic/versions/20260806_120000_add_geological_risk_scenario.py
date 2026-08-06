"""add geological_risk scenario

Revision ID: a3b5c7d9e1f2
Revises: d6adba5112b8
Create Date: 2026-08-06 12:00:00.000000

补充《接入新的数据集并完善各个场景故事.md》（需求 v2.0）定义的第四个场景
geological_risk（地质风险）：
- 原 seed 迁移 d6adba5112b8 仅写入 3 个场景（network_security / power_system /
  flightdeck_operation），缺少地质风险场景；
- 本迁移将 geological_risk 追加到 scenario 表，access_status=ACTUAL（实际接入）。

使用原生 SQL + bindparams，与 d6adba5112b8 风格保持一致，
保证 online / offline（--sql）两种模式均可执行。
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b5c7d9e1f2'
down_revision: Union[str, Sequence[str], None] = 'd6adba5112b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 统一使用固定时间戳，保证迁移可重复执行、结果确定（与 seed 迁移 d6adba5112b8 一致）
SEED_TIME = datetime(2026, 8, 6, tzinfo=timezone.utc)

SCENARIO = {
    "code": "geological_risk",
    "name": "地质风险态势",
    "desc": "滑坡易发性地质风险分类",
    "access": "ACTUAL",
}


def upgrade() -> None:
    """写入地质风险场景（code 唯一约束 uk_scenario_code 兜底重复执行）。"""
    scenario_sql = sa.text(
        "INSERT INTO scenario (code, name, description, access_status, created_at, updated_at) "
        "VALUES (:code, :name, :desc, :access, :created_at, :updated_at)"
    )
    op.execute(scenario_sql.bindparams(
        code=SCENARIO["code"], name=SCENARIO["name"], desc=SCENARIO["desc"],
        access=SCENARIO["access"], created_at=SEED_TIME, updated_at=SEED_TIME,
    ))


def downgrade() -> None:
    """删除地质风险场景（按唯一编码删除）。"""
    op.execute("DELETE FROM scenario WHERE code = 'geological_risk'")
