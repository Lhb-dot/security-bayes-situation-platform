"""backfill_geological_trigger.py — 给地质风险告警事件补 `landslide_trigger`。

问题：地质风险用户工作台「触发因素分布」（`WorkspaceGeological.vue:33-36`）读
`risk_event.raw_features.landslide_trigger`（口径见 docs/首页字段口径说明.md），
但该场景的告警样本由 dis_raw_data / dis_landslides / dis_guaruja_random 推理而来，
这三份数据集都**没有触发因素字段** —— 于是卡片恒为「暂无告警样本」（死区）。

做法：按真实编目数据集 `dis_global_catalog`（唯一带 landslide_trigger 的数据集）
的触发因素**经验分布**，为缺失该字段的地质告警事件补一个触发因素。事件 id 作随机
种子 → 同一条事件每次得到同一个值（可复现、幂等），重复执行不会覆盖已有值。

注意：这是「先让卡片有数据」的演示回填，字段口径不变（仍是
`raw_features.landslide_trigger`）。重新跑 seed_production_data.py 生成新事件后需再执行本脚本。

用法（项目根目录）：
    python scripts/backfill_geological_trigger.py --dry-run   # 只看分布，不写库
    python scripts/backfill_geological_trigger.py             # 写入
    python scripts/backfill_geological_trigger.py --include-unknown  # 连 unknown 一起照搬
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

# GBK 控制台打印中文会 UnicodeEncodeError，统一转 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db import SessionLocal  # noqa: E402
from app.models.dataset import Dataset  # noqa: E402
from app.models.risk_event import RiskEvent  # noqa: E402
from app.models.scenario import Scenario  # noqa: E402
from app.services.training_executor import resolve_dataset_path  # noqa: E402
from app.utils.arff_reader import read_arff  # noqa: E402

TRIGGER_FIELD = "landslide_trigger"
CATALOG_LOGICAL_ID = "dis_global_catalog"
SCENARIO_CODE = "geological_risk"
#: 编目里 unknown / no_apparent_trigger 不是「触发因素」，默认不参与抽样，
#: 否则卡片会出现一块无信息扇区（编目里 unknown 占 14.6%）。
NON_TRIGGER_VALUES = {"unknown", "no_apparent_trigger", ""}
#: 事件 id 作种子再加固定盐，避免与其它脚本的随机流互相影响
SEED_SALT = 20261012


def _catalog_distribution(path: str) -> Counter:
    """从编目 ARFF 读出 landslide_trigger 的真实取值频次。"""
    fields, rows = read_arff(path)
    names = [field["name"] for field in fields]
    if TRIGGER_FIELD not in names:
        raise SystemExit(f"编目文件缺少 {TRIGGER_FIELD} 字段：{path}")
    index = names.index(TRIGGER_FIELD)
    return Counter(str(row[index]).strip() for row in rows if index < len(row))


def main() -> None:
    parser = argparse.ArgumentParser(description="为地质风险告警事件回填触发因素")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="把编目的 unknown / no_apparent_trigger 也计入抽样池",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        catalog = db.query(Dataset).filter(Dataset.logical_id == CATALOG_LOGICAL_ID).first()
        if catalog is None:
            raise SystemExit(f"未找到数据集 {CATALOG_LOGICAL_ID}")
        raw_distribution = _catalog_distribution(resolve_dataset_path(catalog.file_path))

        blocked = set() if args.include_unknown else NON_TRIGGER_VALUES
        pool = Counter({value: count for value, count in raw_distribution.items() if value not in blocked})
        if not pool:
            raise SystemExit("抽样池为空")
        values = list(pool)
        weights = [pool[value] for value in values]
        print(f"编目触发因素分布（{sum(weights)} 条样本，{len(values)} 类）：")
        for value, count in pool.most_common():
            print(f"    {value:<26} {count:>5}  {count / sum(weights) * 100:5.1f}%")

        scenario = db.query(Scenario).filter(Scenario.code == SCENARIO_CODE).first()
        if scenario is None:
            raise SystemExit(f"未找到场景 {SCENARIO_CODE}")
        events = (
            db.query(RiskEvent)
            .filter(RiskEvent.scenario_id == scenario.id)
            .order_by(RiskEvent.id)
            .all()
        )

        filled, skipped = 0, 0
        assigned: Counter = Counter()
        for event in events:
            features = event.raw_features if isinstance(event.raw_features, dict) else {}
            if str(features.get(TRIGGER_FIELD) or "").strip():
                skipped += 1
                continue
            value = random.Random(event.id + SEED_SALT).choices(values, weights=weights, k=1)[0]
            assigned[value] += 1
            filled += 1
            if not args.dry_run:
                # JSONB 不跟踪原地修改，必须整体替换
                event.raw_features = {**features, TRIGGER_FIELD: value}
                db.add(event)

        print(f"\n地质告警事件 {len(events)} 条：待补 {filled} 条，已有值跳过 {skipped} 条")
        for value, count in assigned.most_common():
            print(f"    本次回填 {value:<26} {count:>5}")
        if args.dry_run:
            print("\n[dry-run] 未写库")
        else:
            db.commit()
            print("\n完成：已写库")


if __name__ == "__main__":
    main()
