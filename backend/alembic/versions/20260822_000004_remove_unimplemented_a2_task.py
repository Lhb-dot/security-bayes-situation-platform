"""remove A2WNB task options whose source branches are not implemented"""

import json

import sqlalchemy as sa
from alembic import op


revision = "20260822_000004"
down_revision = "20260822_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = [
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
    op.get_bind().execute(
        sa.text("UPDATE algorithm SET param_schema = CAST(:schema AS jsonb) WHERE code = 'A2WNB'"),
        {"schema": json.dumps(schema, ensure_ascii=False)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE algorithm SET param_schema = CAST(:schema AS jsonb) WHERE code = 'A2WNB'"
        ),
        {"schema": json.dumps([])},
    )
