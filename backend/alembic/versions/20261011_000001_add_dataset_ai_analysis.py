"""add dataset.ai_analysis for cached AI algorithm-fit analysis

数据集「AI 解析」产物按数据集缓存：打开弹窗先读这里，只有用户主动点击
「解析 / 重新解析」才重新调用 AI。与 model_version.ai_evaluation 同构，
整块 JSONB 读改写，结构：{"latest": {markdown, source, generated_at, facts_snapshot, ...}}。

历史数据为 NULL，读取方按空对象处理，无需回填。
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261011_000001"
down_revision = "20260927_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dataset", sa.Column("ai_analysis", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("dataset", "ai_analysis")
