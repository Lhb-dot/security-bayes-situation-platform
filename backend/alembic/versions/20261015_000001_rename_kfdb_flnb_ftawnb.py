"""rename KFDB / FLNB / FTAWNB for the training UI

Revision ID: 20261015_000001
Revises: 20261012_000005
"""
from alembic import op
import sqlalchemy as sa


revision = "20261015_000001"
down_revision = "20261012_000005"
branch_labels = None
depends_on = None


NEW_NAMES = {
    "KFDB": "K自由依赖贝叶斯分类器（KFDB）",
    "FLNB": "基于频率的消极加权朴素贝叶斯（FLNB）",
    "FTAWNB": "基于概率微调的属性加权朴素贝叶斯（FTAWNB）",
}

OLD_NAMES = {
    "KFDB": "K-Free依赖贝叶斯分类器(KFDB)",
    "FLNB": "频率懒惰朴素贝叶斯(FLNB)",
    "FTAWNB": "属性加权朴素贝叶斯微调(FTAWNB)",
}


def _update_names(names: dict[str, str]) -> None:
    connection = op.get_bind()
    statement = sa.text(
        "UPDATE algorithm SET display_name = :display_name WHERE code = :code"
    )
    for code, display_name in names.items():
        connection.execute(statement, {"code": code, "display_name": display_name})


def upgrade() -> None:
    _update_names(NEW_NAMES)


def downgrade() -> None:
    _update_names(OLD_NAMES)
