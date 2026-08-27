"""expose PMWNB discretization parameters wired by its filtered service"""

import json

import sqlalchemy as sa
from alembic import op


revision = "20260822_000005"
down_revision = "20260822_000004"
branch_labels = None
depends_on = None


PMWNB_SCHEMA = [
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
    op.get_bind().execute(
        sa.text("UPDATE algorithm SET param_schema = CAST(:schema AS jsonb) WHERE code = 'PMWNB'"),
        {"schema": json.dumps(PMWNB_SCHEMA, ensure_ascii=False)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE algorithm SET param_schema = CAST('[]' AS jsonb) WHERE code = 'PMWNB'"),
    )
