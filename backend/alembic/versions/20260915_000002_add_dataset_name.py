"""add dataset display name column

数据集展示名：用户上传时可自填的中文名。
为空时由 app.services.constants.dataset_display_name(logical_id) 兜底，
因此平台预置数据集无需回填（保持 NULL 即可）。
"""

import sqlalchemy as sa
from alembic import op


revision = "20260915_000002"
down_revision = "20260915_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dataset", sa.Column("name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("dataset", "name")
