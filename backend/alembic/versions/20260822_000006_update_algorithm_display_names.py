"""update algorithm display_name to 「中文名(英文缩写)」 format"""

import sqlalchemy as sa
from alembic import op


revision = "20260822_000006"
down_revision = "20260822_000005"
branch_labels = None
depends_on = None


# 需求：算法显示名统一为「中文名(英文缩写)」格式（原 display_name 为占位/旧译名）。
DISPLAY_NAMES = {
    "A2WNB": "属性增广和加权朴素贝叶斯(A2WNB)",
    "MAWNB": "多视图加权朴素贝叶斯(MAWNB)",
    "EMAWNB": "增强多视图朴素贝叶斯(EMAWNB)",
    "CAVWNB": "类依赖属性值加权朴素贝叶斯(CAVWNB)",
    "PMWNB": "矩阵视图加权朴素贝叶斯(PMWNB)",
}

# 回滚时恢复的旧 display_name（20260822_000002 之后的状态）。
OLD_DISPLAY_NAMES = {
    "A2WNB": "A²加权朴素贝叶斯",
    "MAWNB": "模型平均加权朴素贝叶斯",
    "EMAWNB": "指数移动平均加权朴素贝叶斯",
    "CAVWNB": "CAVWNB 类别自适应加权朴素贝叶斯",
    "PMWNB": "PMWNB 概率均值加权朴素贝叶斯",
}


def upgrade() -> None:
    conn = op.get_bind()
    for code, name in DISPLAY_NAMES.items():
        conn.execute(
            sa.text("UPDATE algorithm SET display_name = :name WHERE code = :code"),
            {"code": code, "name": name},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for code, name in OLD_DISPLAY_NAMES.items():
        conn.execute(
            sa.text("UPDATE algorithm SET display_name = :name WHERE code = :code"),
            {"code": code, "name": name},
        )
