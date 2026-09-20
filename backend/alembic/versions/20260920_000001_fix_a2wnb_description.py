"""correct the A2WNB description to match the delivered implementation

`algorithm.description` 会在「模型训练」页直接展示。A2WNB 原文案声称
「按属性权重指数自适应加权」，但交付的算法源码里没有属性加权阶段：
`A2WNB.java` 引用的 `weka.classifiers.bayes.WANBIA.WANBIA` 未随源码交付，
平台以 `backend/java/compat/WANBIA.java`（`extends NaiveBayes` 的空壳）顶替；
`RODE.java` 的 `m_Weights` 恒为 1（ACC/CLL/AUC 三种加权方案均被注释）。
即实际执行的是「RODE 属性增广 + 朴素贝叶斯融合判定」。

`display_name` 保持不变：A²WNB 的官方名称即 Attribute augmented and weighted NB
（见仓库根目录 nb_alg_summary.md 第 2 节），中文名是其翻译，改名会与论文脱节。
仅改文案，不改任何算法实现或参数定义。
"""

import sqlalchemy as sa
from alembic import op


revision = "20260920_000001"
down_revision = "20260915_000002"
branch_labels = None
depends_on = None


NEW_DESCRIPTION = (
    "Attribute augmented and weighted NB，"
    "RODE 为每个属性生成补充属性后完成融合判定"
)

OLD_DESCRIPTION = "Adaptive Attribute Weighted Naive Bayes，按属性权重指数自适应加权"


def _set_description(description: str) -> None:
    op.get_bind().execute(
        sa.text("UPDATE algorithm SET description = :description WHERE code = 'A2WNB'"),
        {"description": description},
    )


def upgrade() -> None:
    _set_description(NEW_DESCRIPTION)


def downgrade() -> None:
    _set_description(OLD_DESCRIPTION)
