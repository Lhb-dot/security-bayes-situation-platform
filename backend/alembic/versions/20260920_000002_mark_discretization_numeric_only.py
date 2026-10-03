"""mark discretization parameters as numeric-feature-only

`discrete_method` / `discrete_bins` 由平台的 `FilteredClassifierWithDiscretize`
（Weka `Discretize`）消费，只对数值特征分箱。数据集本身已是离散属性时过滤器空转 ——
实测在 `dis_r*` 系列（全 enum）上 bins=2 与 bins=100 的指标与模型字节几乎完全一致。

标记 `requires_numeric_features` 后：
- `validate_params_schema` 对无数值特征的数据集跳过这两项（不再必填）；
- `strip_inapplicable_params` 把它们从模型训练参数里剔除，记录的是真实生效的参数；
- 前端训练表单据此隐藏这两项，避免让人填一个不起作用的参数。

仅改参数声明，不改任何算法实现，也不改动已训练模型。
"""

import sqlalchemy as sa
from alembic import op


revision = "20260920_000002"
down_revision = "20260920_000001"
branch_labels = None
depends_on = None


_ADD_FLAG = sa.text(
    """
    UPDATE algorithm
    SET param_schema = (
        SELECT jsonb_agg(
            CASE
                WHEN item ->> 'name' IN ('discrete_method', 'discrete_bins')
                    THEN item || '{"requires_numeric_features": true}'::jsonb
                ELSE item
            END
            ORDER BY ordinality
        )
        FROM jsonb_array_elements(param_schema) WITH ORDINALITY AS t(item, ordinality)
    )
    WHERE jsonb_typeof(param_schema) = 'array'
      AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(param_schema) e
          WHERE e ->> 'name' IN ('discrete_method', 'discrete_bins')
      )
    """
)

_REMOVE_FLAG = sa.text(
    """
    UPDATE algorithm
    SET param_schema = (
        SELECT jsonb_agg(item - 'requires_numeric_features' ORDER BY ordinality)
        FROM jsonb_array_elements(param_schema) WITH ORDINALITY AS t(item, ordinality)
    )
    WHERE jsonb_typeof(param_schema) = 'array'
      AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(param_schema) e
          WHERE e ? 'requires_numeric_features'
      )
    """
)


def upgrade() -> None:
    op.get_bind().execute(_ADD_FLAG)


def downgrade() -> None:
    op.get_bind().execute(_REMOVE_FLAG)
