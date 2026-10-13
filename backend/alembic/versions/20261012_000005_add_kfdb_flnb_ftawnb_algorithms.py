"""register KFDB / FLNB / FTAWNB as trainable algorithms

三个论文算法的平台接入（源码见 backend/java/algorithm-src/NB/{KFDB,FLNB,FTAWNB}，
编译进共用的 nb-algorithm-service.jar，端口 12315）。

- KFDB：K-Free Dependence Bayesian Classifier（Meng/Zhang 等，TNNLS 2026）。
  适配器 weka.classifiers.zh.KFDB.KFDB 包装作者仓库的 KFDB.wdBayesOnlinePYP。
- FLNB：Frequency-based Lazy Naive Bayes（Zhang/Jiang）。作者仓库提供 poly / log
  两个相似度版本，平台通过 weight_scheme 参数选择，默认 poly。
- FTAWNB：Fine Tuning Attribute Weighted Naive Bayes（Zhang/Jiang，Neurocomputing 2021）。

三者都按离散属性工作，数值特征由平台前置离散化；因此离散化参数与既有算法一致，
并带 requires_numeric_features 标记（纯离散数据集上不生效，见 20260920_000002）。
display_name 采用既有「中文名(英文缩写)」格式（见 20260822_000006）。
使用原生 SQL + CAST(... AS jsonb)，online / offline 两种模式均可执行。
"""
import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "20261012_000005"
down_revision = "20261012_000004"
branch_labels = None
depends_on = None


def _enum(name, label, default, values, options, description):
    return {
        "name": name,
        "label": label,
        "type": "enum",
        "required": True,
        "default": default,
        "enum_values": values,
        "options": options,
        "description": description,
    }


DISCRETE_METHOD = {
    "name": "discrete_method",
    "label": "离散化方式",
    "type": "enum",
    "required": True,
    "default": "equal_width",
    "enum_values": ["equal_width", "equal_freq"],
    "options": [
        {"value": "equal_width", "label": "等宽分箱"},
        {"value": "equal_freq", "label": "等频分箱"},
    ],
    "description": "训练前对数值特征使用的离散化方式",
    "requires_numeric_features": True,
}

DISCRETE_BINS = {
    "name": "discrete_bins",
    "label": "分箱数量",
    "type": "int",
    "required": True,
    "default": 10,
    "min": 2,
    "max": 100,
    "step": 1,
    "description": "训练前数值特征的分箱数量",
    "requires_numeric_features": True,
}

KFDB_SCHEMA = [
    DISCRETE_METHOD,
    DISCRETE_BINS,
    _enum(
        "model_score", "结构评分", "KFDB_MSE",
        ["KFDB_MSE", "KFDB_ACC"],
        [{"value": "KFDB_MSE", "label": "均方误差"}, {"value": "KFDB_ACC", "label": "分类精度"}],
        "依赖结构学习的评分准则",
    ),
    {
        "name": "max_parents",
        "label": "最大父属性数",
        "type": "int",
        "required": True,
        "default": 1,
        "min": 1,
        "max": 3,
        "step": 1,
        "description": "每个属性最多允许的父属性个数（论文中的 k）",
    },
]

FLNB_SCHEMA = [
    DISCRETE_METHOD,
    DISCRETE_BINS,
    _enum(
        "weight_scheme", "相似度加权", "poly",
        ["poly", "log"],
        [{"value": "poly", "label": "多项式相似度"}, {"value": "log", "label": "对数相似度"}],
        "频率相似度的加权方式",
    ),
]

FTAWNB_SCHEMA = [DISCRETE_METHOD, DISCRETE_BINS]

ALGORITHMS = [
    {
        "code": "KFDB",
        "display_name": "K-Free依赖贝叶斯分类器(KFDB)",
        "description": "K-Free Dependence Bayesian Classifier，为每个属性学习最多 k 个父属性后做概率推断",
        "param_schema": KFDB_SCHEMA,
    },
    {
        "code": "FLNB",
        "display_name": "频率懒惰朴素贝叶斯(FLNB)",
        "description": "Frequency-based Lazy Naive Bayes，按测试样本与训练样本的频率相似度加权估计条件概率",
        "param_schema": FLNB_SCHEMA,
    },
    {
        "code": "FTAWNB",
        "display_name": "属性加权朴素贝叶斯微调(FTAWNB)",
        "description": "Fine Tuning Attribute Weighted Naive Bayes，用属性与类别的互信息微调属性权重",
        "param_schema": FTAWNB_SCHEMA,
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    insert = sa.text(
        "INSERT INTO algorithm (code, display_name, description, param_schema, status, created_at) "
        "VALUES (:code, :display_name, :description, CAST(:param_schema AS jsonb), :status, :created_at)"
    )
    for row in ALGORITHMS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM algorithm WHERE code = :code"), {"code": row["code"]}
        ).scalar()
        if exists:
            continue
        conn.execute(insert, {
            "code": row["code"],
            "display_name": row["display_name"],
            "description": row["description"],
            "param_schema": json.dumps(row["param_schema"], ensure_ascii=False),
            "status": "AVAILABLE",
            "created_at": datetime.now(timezone.utc),
        })


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM algorithm WHERE code IN ('KFDB', 'FLNB', 'FTAWNB')")
    )
