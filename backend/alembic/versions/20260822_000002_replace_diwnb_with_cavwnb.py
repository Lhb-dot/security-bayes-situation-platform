"""replace the D-prefixed algorithm registration with CAVWNB"""

import json

import sqlalchemy as sa
from alembic import op


revision = "20260822_000002"
down_revision = "20260822_000001"
branch_labels = None
depends_on = None


CAVWNB_SCHEMA = [
    {
        "name": "discrete_method", "type": "enum", "required": False,
        "default": "equal_width", "enum_values": ["equal_width", "equal_freq"],
        "label": "离散化方式", "options": [
            {"value": "equal_width", "label": "等宽分箱"},
            {"value": "equal_freq", "label": "等频分箱"},
        ],
    },
    {
        "name": "objective", "type": "enum", "required": False,
        "default": "CLL", "enum_values": ["CLL", "MSE"],
        "label": "目标函数", "options": [
            {"value": "CLL", "label": "条件对数似然"},
            {"value": "MSE", "label": "均方误差"},
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM algorithm WHERE code = 'CAVWNB'")
    ).scalar()
    if exists:
        conn.execute(sa.text("DELETE FROM algorithm WHERE code = 'DIWNB'"))
    else:
        conn.execute(
            sa.text(
                "UPDATE algorithm SET code = :code, display_name = :display_name, "
                "description = :description, param_schema = CAST(:param_schema AS jsonb) "
                "WHERE code = 'DIWNB'"
            ),
            {
                "code": "CAVWNB",
                "display_name": "CAVWNB 类别自适应加权朴素贝叶斯",
                "description": "Category-Adaptive Variable Weighted Naive Bayes，使用外部 Java/Weka 真实实现",
                "param_schema": json.dumps(CAVWNB_SCHEMA, ensure_ascii=False),
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE algorithm SET code = 'DIWNB', display_name = '差分加权朴素贝叶斯' "
            "WHERE code = 'CAVWNB'"
        )
    )
