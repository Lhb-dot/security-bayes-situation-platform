"""register only parameters wired to the real Java training services"""

import json

import sqlalchemy as sa
from alembic import op


revision = "20260822_000003"
down_revision = "20260822_000002"
branch_labels = None
depends_on = None


def _enum(name, label, default, values, options, description):
    return {
        "name": name,
        "label": label,
        "type": "enum",
        "required": True,
        "default": default,
        "enum_values": values,
        "options": options,
        "description": description,
    }


def _int(name, label, default, minimum, maximum, description):
    return {
        "name": name,
        "label": label,
        "type": "int",
        "required": True,
        "default": default,
        "min": minimum,
        "max": maximum,
        "step": 1,
        "description": description,
    }


DISCRETE_METHOD = _enum(
    "discrete_method",
    "离散化方式",
    "equal_width",
    ["equal_width", "equal_freq"],
    [
        {"value": "equal_width", "label": "等宽分箱"},
        {"value": "equal_freq", "label": "等频分箱"},
    ],
    "训练前对数值特征使用的 Weka 离散化方式",
)
DISCRETE_BINS = _int(
    "discrete_bins", "分箱数量", 10, 2, 100, "训练前数值特征的分箱数量"
)

CAV_SCHEMA = [
    DISCRETE_METHOD,
    DISCRETE_BINS,
    _enum(
        "objective",
        "目标函数",
        "CLL",
        ["CLL", "MSE"],
        [
            {"value": "CLL", "label": "条件对数似然"},
            {"value": "MSE", "label": "均方误差"},
        ],
        "CAVWNB 权重优化目标",
    ),
    _enum(
        "regularizer",
        "正则化方式",
        "L2",
        ["None", "L2"],
        [{"value": "None", "label": "无正则化"}, {"value": "L2", "label": "L2 正则化"}],
        "CAVWNB 权重优化正则化方式",
    ),
    {
        "name": "regularization_lambda",
        "label": "正则化系数",
        "type": "float",
        "required": True,
        "default": 1.0,
        "min": 0.0,
        "max": 100.0,
        "step": 0.1,
        "description": "L2 正则化系数；选择无正则化时该值不参与目标函数计算",
    },
]

A2_SCHEMA = [
    DISCRETE_METHOD,
    DISCRETE_BINS,
    _int(
        "rode_task",
        "RODE 权重任务",
        1,
        1,
        4,
        "RODE 内部权重评估任务：1-4 对应源码中的任务分支",
    ),
]

ALGORITHM_SCHEMAS = {
    "A2WNB": A2_SCHEMA,
    "MAWNB": [DISCRETE_METHOD, DISCRETE_BINS],
    "EMAWNB": [DISCRETE_METHOD, DISCRETE_BINS],
    "CAVWNB": CAV_SCHEMA,
    "PMWNB": [],
}


def upgrade() -> None:
    conn = op.get_bind()
    for code, schema in ALGORITHM_SCHEMAS.items():
        conn.execute(
            sa.text(
                "UPDATE algorithm SET param_schema = CAST(:schema AS jsonb) "
                "WHERE code = :code"
            ),
            {"code": code, "schema": json.dumps(schema, ensure_ascii=False)},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for code in ALGORITHM_SCHEMAS:
        conn.execute(
            sa.text("UPDATE algorithm SET param_schema = CAST('[]' AS jsonb) WHERE code = :code"),
            {"code": code},
        )
