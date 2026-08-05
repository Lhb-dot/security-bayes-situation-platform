"""create core tables

Revision ID: 85b25ac03ba5
Revises:
Create Date: 2026-08-02 12:40:08.254770

初始基线迁移：直接依据 SQLAlchemy ORM 模型（backend/app/models/，12 张表）生成
表结构，保证迁移脚本与模型零漂移。后续结构变更统一走
`alembic revision --autogenerate` 生成增量迁移。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import Base
import app.models  # noqa: F401  导入以把全部 12 张表注册到 Base.metadata


# revision identifiers, used by Alembic.
revision: str = '85b25ac03ba5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建全部核心表（对应《数据库设计文档v2》2.1 ~ 2.12）。"""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """删除全部核心表。"""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
