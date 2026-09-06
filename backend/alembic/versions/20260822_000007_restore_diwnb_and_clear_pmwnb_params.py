"""restore DIWNB as a registered algorithm and clear PMWNB discretization params"""

import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "20260822_000007"
down_revision = "20260822_000006"
branch_labels = None
depends_on = None


# DIWNB 前置等宽离散参数（与 A2WNB/MAWNB/EMAWNB 一致；DIWNB_HE 首视图 AVFWNB 只接受离散输入）
DIWNB_PARAM_SCHEMA = [
    {
        "name": "discrete_method",
        "label": "离散化方式",
        "type": "enum",
        "required": True,
        "default": "equal_width",
        "enum_values": ["equal_width", "equal_freq"],
        "options": [
            {"value": "equal_width", "label": "等宽分箱"},
            {"value": "equal_freq", "label": "等频分箱"},
        ],
        "description": "训练前对数值特征使用的 Weka 离散化方式",
    },
    {
        "name": "discrete_bins",
        "label": "分箱数量",
        "type": "int",
        "required": True,
        "default": 10,
        "min": 2,
        "max": 100,
        "step": 1,
        "description": "训练前数值特征的分箱数量",
    },
]

# 迁移前 PMWNB 的离散化参数（20260822_000005 写入），供 downgrade 恢复。
PMWNB_OLD_SCHEMA = [
    {
        "name": "discrete_method",
        "label": "离散化方式",
        "type": "enum",
        "required": True,
        "default": "equal_width",
        "enum_values": ["equal_width", "equal_freq"],
        "options": [
            {"value": "equal_width", "label": "等宽分箱"},
            {"value": "equal_freq", "label": "等频分箱"},
        ],
        "description": "PMWNB 训练前对数值特征使用的 Weka 离散化方式",
    },
    {
        "name": "discrete_bins",
        "label": "分箱数量",
        "type": "int",
        "required": True,
        "default": 10,
        "min": 2,
        "max": 100,
        "step": 1,
        "description": "PMWNB 训练前数值特征的分箱数量",
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    # PMWNB 内部自带 EWD+MDLP 离散，去掉平台层的离散化参数
    conn.execute(
        sa.text("UPDATE algorithm SET param_schema = CAST('[]' AS jsonb) WHERE code = 'PMWNB'")
    )
    # 恢复 DIWNB 为第 6 个可训练算法
    exists = conn.execute(sa.text("SELECT 1 FROM algorithm WHERE code = 'DIWNB'")).scalar()
    if not exists:
        conn.execute(
            sa.text(
                "INSERT INTO algorithm (code, display_name, description, param_schema, status, created_at) "
                "VALUES (:code, :display_name, :description, CAST(:param_schema AS jsonb), :status, :created_at)"
            ),
            {
                "code": "DIWNB",
                "display_name": "双视图示例加权朴素贝叶斯(DIWNB)",
                "description": "Dual-view Instance Weighted Naive Bayes，KNN 生成标签/概率视图后做实例加权（α=15、β=5）",
                "param_schema": json.dumps(DIWNB_PARAM_SCHEMA, ensure_ascii=False),
                "status": "AVAILABLE",
                "created_at": datetime.now(timezone.utc),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM algorithm WHERE code = 'DIWNB'"))
    conn.execute(
        sa.text(
            "UPDATE algorithm SET param_schema = CAST(:schema AS jsonb) WHERE code = 'PMWNB'"
        ),
        {"schema": json.dumps(PMWNB_OLD_SCHEMA, ensure_ascii=False)},
    )
