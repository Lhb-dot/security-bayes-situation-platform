"""seed scenario and algorithm

Revision ID: d6adba5112b8
Revises: 85b25ac03ba5
Create Date: 2026-08-02 12:40:31.456836

静态基础数据初始化（对应《数据库设计文档v2》第 8 章）：
- scenario：3 个场景（network_security / power_system / flightdeck_operation）
- algorithm：5 个算法（A2WNB / MAWNB / EMAWNB / CAVWNB / PMWNB）

display_name / param_schema 待算法组确认后以增量迁移更新，Seed 阶段先写入编码与状态。
使用原生 SQL + ::jsonb 强转，保证 online / offline（--sql）两种模式均可执行。
"""
import json
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6adba5112b8'
down_revision: Union[str, Sequence[str], None] = '85b25ac03ba5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 统一使用固定时间戳，保证迁移可重复执行、结果确定
SEED_TIME = datetime(2026, 8, 2, tzinfo=timezone.utc)

SCENARIOS = [
    {"code": "network_security", "name": "网络安全态势",
     "desc": "网络入侵流量分类", "access": "ACTUAL"},
    {"code": "power_system", "name": "电力系统态势",
     "desc": "电力停电风险", "access": "ACTUAL"},
    {"code": "flightdeck_operation", "name": "舰面调度态势",
     "desc": "航母舰面调度风险", "access": "ACTUAL"},
]

ALGORITHMS = [
    {"code": "A2WNB", "desc": "矩阵加权贝叶斯系"},
    {"code": "MAWNB", "desc": "矩阵加权贝叶斯系"},
    {"code": "EMAWNB", "desc": "矩阵加权贝叶斯系"},
    {"code": "CAVWNB", "desc": "矩阵加权贝叶斯系"},
    {"code": "PMWNB", "desc": "当前项目已接入算法"},
]


def upgrade() -> None:
    """写入场景与算法静态基础数据。"""
    scenario_sql = sa.text(
        "INSERT INTO scenario (code, name, description, access_status, created_at, updated_at) "
        "VALUES (:code, :name, :desc, :access, :created_at, :updated_at)"
    )
    for row in SCENARIOS:
        op.execute(scenario_sql.bindparams(
            code=row["code"], name=row["name"], desc=row["desc"],
            access=row["access"], created_at=SEED_TIME, updated_at=SEED_TIME,
        ))

    algorithm_sql = sa.text(
        "INSERT INTO algorithm (code, display_name, description, param_schema, status, created_at) "
        "VALUES (:code, :display_name, :desc, CAST(:param_schema AS jsonb), :status, :created_at)"
    )
    for row in ALGORITHMS:
        display_name = "PMWNB 矩阵加权贝叶斯" if row["code"] == "PMWNB" else "（待算法组确认）"
        op.execute(algorithm_sql.bindparams(
            code=row["code"], display_name=display_name, desc=row["desc"],
            param_schema=json.dumps([]), status="AVAILABLE", created_at=SEED_TIME,
        ))


def downgrade() -> None:
    """删除 seed 数据（按唯一编码删除）。"""
    op.execute("DELETE FROM algorithm WHERE code IN "
               "('A2WNB', 'MAWNB', 'EMAWNB', 'CAVWNB', 'PMWNB')")
    op.execute("DELETE FROM scenario WHERE code IN "
               "('network_security', 'power_system', 'flightdeck_operation')")

