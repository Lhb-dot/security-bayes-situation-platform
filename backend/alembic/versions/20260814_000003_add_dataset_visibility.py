"""add dataset visibility (data ownership hierarchy)

Revision ID: 20260814_000003
Revises: 20260814_000002
Create Date: 2026-08-14 00:00:03.000000

三级角色数据可见性分级：
- platform（平台数据）：最外层管理员管理，作为各场景基线数据
- company（公司数据）：场景管理员上传，最外层管理员不可见
- personal（个人数据）：场景用户上传，场景管理员与最外层都不可见
"""
import sqlalchemy as sa
from alembic import op

revision = "20260814_000003"
down_revision = "20260814_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dataset",
        sa.Column("visibility", sa.String(16), nullable=False, server_default="platform"),
    )
    op.add_column(
        "dataset",
        sa.Column("uploader_role", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dataset", "uploader_role")
    op.drop_column("dataset", "visibility")
