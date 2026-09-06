"""update algorithm param_schema and display_name

Revision ID: 20260808_000001
Revises: a3b5c7d9e1f2
Create Date: 2026-08-08 00:00:01.000000

需求 6.6.3：训练参数由算法注册的 param_schema 动态渲染。
Seed 迁移 d6adba5112b8 中 5 个算法的 param_schema 为 []、display_name 为占位文案，
本迁移把前端算法注册表（mockApi algorithmRegistry）中对应的参数定义与名称落到数据库：

- A2WNB / MAWNB / EMAWNB / DIWNB：各自公开训练参数（离散化方式、分箱数量、平滑系数 + 专属参数）
- PMWNB：Java 实现（weka PMWNB）不暴露超参数，param_schema 保持 []，
  训练时使用服务内置默认参数（见 training_executor.execute_pmwnb_training）。

param_schema 条目结构兼容 app.utils.common.validate_params_schema：
    {name, type(int|float|bool|enum|str), required, default, min, max, enum_values}
并附加前端渲染所需的扩展键（label / step / options / description），校验逻辑忽略多余键。
使用原生 SQL + CAST(... AS jsonb)，保证 online / offline（--sql）两种模式均可执行。
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260808_000001'
down_revision: Union[str, Sequence[str], None] = 'a3b5c7d9e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name, label, default, values, options, description):
    """离散化方式等枚举参数：枚举值 + 前端选项标签。"""
    return {
        "name": name, "label": label, "type": "enum", "required": True,
        "default": default, "enum_values": values, "options": options,
        "description": description,
    }


def _num(name, label, default, ptype, min_v, max_v, step, description):
    """数值参数（int/float），带范围与步长。"""
    return {
        "name": name, "label": label, "type": ptype, "required": True,
        "default": default, "min": min_v, "max": max_v, "step": step,
        "description": description,
    }


DISCRETE_METHOD = _enum(
    "discrete_method", "离散化方式", "equal_width",
    ["equal_width", "equal_freq"],
    [{"value": "equal_width", "label": "等宽分箱"},
     {"value": "equal_freq", "label": "等频分箱"}],
    "数值特征离散化策略",
)
DISCRETE_BINS = _num("discrete_bins", "分箱数量", 10, "int", 3, 20, 1,
                     "数值特征离散化的分箱个数")
SMOOTHING = _num("smoothing", "拉普拉斯平滑", 1.0, "float", 0, 2, 0.1,
                 "条件概率平滑参数")

ALGORITHMS = [
    {
        "code": "A2WNB",
        "display_name": "A²加权朴素贝叶斯",
        "description": "Adaptive Attribute Weighted Naive Bayes，按属性权重指数自适应加权"
                       "（占位训练，算法实现待算法组交付）",
        "param_schema": [
            DISCRETE_METHOD, DISCRETE_BINS, SMOOTHING,
            _num("weight_exponent", "属性权重指数", 1.0, "float", 0.5, 3, 0.1,
                 "属性加权时的权重指数"),
        ],
    },
    {
        "code": "MAWNB",
        "display_name": "模型平均加权朴素贝叶斯",
        "description": "Model Averaging Weighted Naive Bayes，多个子模型加权平均"
                       "（占位训练，算法实现待算法组交付）",
        "param_schema": [
            DISCRETE_METHOD, DISCRETE_BINS, SMOOTHING,
            _num("ensemble_size", "子模型数量", 5, "int", 1, 10, 1, "集成子模型的数量"),
        ],
    },
    {
        "code": "EMAWNB",
        "display_name": "指数移动平均加权朴素贝叶斯",
        "description": "Exponential Moving Average Weighted Naive Bayes，利用滑动窗口估计加权概率"
                       "（占位训练，算法实现待算法组交付）",
        "param_schema": [
            DISCRETE_METHOD, DISCRETE_BINS, SMOOTHING,
            _num("window_size", "移动窗口大小", 10, "int", 2, 50, 1,
                 "指数移动平均的观测窗口"),
        ],
    },
    {
        "code": "CAVWNB",
        "display_name": "CAVWNB 类别自适应加权朴素贝叶斯",
        "description": "Category-Adaptive Variable Weighted Naive Bayes，使用外部 Java/Weka 真实实现",
        "param_schema": [
            DISCRETE_METHOD, DISCRETE_BINS, SMOOTHING,
            _enum("objective", "目标函数", "CLL", ["CLL", "MSE"],
                  [{"value": "CLL", "label": "条件对数似然"}, {"value": "MSE", "label": "均方误差"}],
                  "CAVWNB 权重优化目标"),
        ],
    },
    {
        "code": "PMWNB",
        "display_name": "PMWNB 概率均值加权朴素贝叶斯",
        "description": "Probability Mean Weighted Naive Bayes，当前项目已接入的真实算法"
                       "（weka 实现，通过 Java 服务调用训练）；不暴露公开训练超参数，"
                       "使用服务内置默认参数",
        "param_schema": [],
    },
]


def upgrade() -> None:
    sql = sa.text(
        "UPDATE algorithm SET display_name = :display_name, description = :desc, "
        "param_schema = CAST(:param_schema AS jsonb) WHERE code = :code"
    )
    for row in ALGORITHMS:
        op.execute(sql.bindparams(
            code=row["code"], display_name=row["display_name"],
            desc=row["description"], param_schema=json.dumps(row["param_schema"]),
        ))


def downgrade() -> None:
    """回滚：恢复 seed 占位文案与空 param_schema。"""
    sql = sa.text(
        "UPDATE algorithm SET display_name = :display_name, description = :desc, "
        "param_schema = CAST(:param_schema AS jsonb) WHERE code = :code"
    )
    for code in ("A2WNB", "MAWNB", "EMAWNB", "CAVWNB"):
        op.execute(sql.bindparams(
            code=code, display_name="（待算法组确认）", desc="矩阵加权贝叶斯系",
            param_schema=json.dumps([]),
        ))
    op.execute(sql.bindparams(
        code="PMWNB", display_name="PMWNB 矩阵加权贝叶斯", desc="当前项目已接入算法",
        param_schema=json.dumps([]),
    ))
