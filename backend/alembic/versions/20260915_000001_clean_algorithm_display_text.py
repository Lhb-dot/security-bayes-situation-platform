"""clean developer-facing wording from algorithm descriptions and parameter help

「模型训练」页会直接展示 algorithm.description 与 param_schema[].description，
原文本包含面向开发过程的表述（「（占位训练，算法实现待算法组交付）」
「使用外部 Java/Weka 真实实现」「Weka 离散化方式」等），不适合在业务界面展示，
统一改写为面向业务用户的算法说明。仅改文案，不改任何算法实现或参数定义。
"""

import sqlalchemy as sa
from alembic import op


revision = "20260915_000001"
down_revision = "20260914_000002"
branch_labels = None
depends_on = None


# 清理后的算法说明（面向业务用户）
NEW_DESCRIPTIONS = {
    "A2WNB": "Adaptive Attribute Weighted Naive Bayes，按属性权重指数自适应加权",
    "MAWNB": "Model Averaging Weighted Naive Bayes，多个子模型加权平均",
    "EMAWNB": "Exponential Moving Average Weighted Naive Bayes，利用滑动窗口估计加权概率",
    "CAVWNB": "Category-Adaptive Variable Weighted Naive Bayes",
    "PMWNB": "Probability Mean Weighted Naive Bayes",
    "DIWNB": "Dual-view Instance Weighted Naive Bayes，KNN 生成标签/概率视图后做实例加权",
}

# 迁移前的实际文案，供 downgrade 恢复
OLD_DESCRIPTIONS = {
    "A2WNB": "Adaptive Attribute Weighted Naive Bayes，按属性权重指数自适应加权"
             "（占位训练，算法实现待算法组交付）",
    "MAWNB": "Model Averaging Weighted Naive Bayes，多个子模型加权平均"
             "（占位训练，算法实现待算法组交付）",
    "EMAWNB": "Exponential Moving Average Weighted Naive Bayes，利用滑动窗口估计加权概率"
              "（占位训练，算法实现待算法组交付）",
    "CAVWNB": "Category-Adaptive Variable Weighted Naive Bayes，使用外部 Java/Weka 真实实现",
    "PMWNB": "Probability Mean Weighted Naive Bayes，当前项目已接入的真实算法"
             "（weka 实现，通过 Java 服务调用训练）；不暴露公开训练超参数，使用服务内置默认参数",
    "DIWNB": "Dual-view Instance Weighted Naive Bayes，KNN 生成标签/概率视图后做实例加权"
             "（α=15、β=5）",
}

PARAM_HELP_OLD = "训练前对数值特征使用的 Weka 离散化方式"
PARAM_HELP_NEW = "训练前对数值特征使用的离散化方式"


def _rewrite_param_help(old: str, new: str) -> None:
    """jsonb 文本替换：只替换参数说明中的目标短语，保留其余结构。"""
    op.get_bind().execute(
        sa.text(
            "UPDATE algorithm "
            "SET param_schema = REPLACE(param_schema::text, :old, :new)::jsonb "
            "WHERE param_schema::text LIKE '%' || :old || '%'"
        ),
        {"old": old, "new": new},
    )


def upgrade() -> None:
    conn = op.get_bind()
    for code, description in NEW_DESCRIPTIONS.items():
        conn.execute(
            sa.text("UPDATE algorithm SET description = :description WHERE code = :code"),
            {"code": code, "description": description},
        )
    _rewrite_param_help(PARAM_HELP_OLD, PARAM_HELP_NEW)


def downgrade() -> None:
    conn = op.get_bind()
    for code, description in OLD_DESCRIPTIONS.items():
        conn.execute(
            sa.text("UPDATE algorithm SET description = :description WHERE code = :code"),
            {"code": code, "description": description},
        )
    _rewrite_param_help(PARAM_HELP_NEW, PARAM_HELP_OLD)
