"""rename model_version.is_default to is_recommended (drop unique index)

「默认模型」改名「推荐模型」（2026-10 定稿）：

- 语义从「唯一默认」变为「推荐使用」，同一（scenario_id, dataset_id）
  允许同时推荐多个模型，因此删除部分唯一索引 uk_mv_default。
- 列 is_default -> is_recommended，存量数据原样保留（原默认即推荐）。
"""

import sqlalchemy as sa
from alembic import op

revision = "20261012_000002"
down_revision = "20261012_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uk_mv_default", table_name="model_version")
    op.alter_column(
        "model_version",
        "is_default",
        new_column_name="is_recommended",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "model_version",
        "is_recommended",
        new_column_name="is_default",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.create_index(
        "uk_mv_default",
        "model_version",
        ["scenario_id", "dataset_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
