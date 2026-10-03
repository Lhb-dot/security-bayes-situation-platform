"""backfill_dataset_samples.py — 用 ARFF 源文件同步数据集的字段样例值与枚举值域。

已有数据集在旧版 seed 注册时 fields_schema 有两处偏差：
1. 没有 sample_values（V3.0 §3.1.4 要求）；
2. enum_values 被剥掉了 ARFF 里的转义引号 —— 而 Weka 实际认的枚举值是**带引号**的，
   于是样本库取到的值（带引号）提交后必然被推理输入校验拒掉（「不在枚举值域内」）。

本脚本复用 backend/app/utils/arff_reader.py 重新解析 data/ 下的 ARFF，
按字段名对齐合并 sample_values 与 enum_values，幂等（重复执行结果一致）。

用法（项目根目录）：
    python scripts/backfill_dataset_samples.py            # 写入
    python scripts/backfill_dataset_samples.py --dry-run  # 只看差异，不写库
"""
import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

from app.db import SessionLocal  # noqa: E402
from app.models.dataset import Dataset  # noqa: E402
from app.services.training_executor import resolve_dataset_path  # noqa: E402
from app.utils.arff_reader import (  # noqa: E402
    enrich_sample_values,
    read_arff,
    sync_enum_values,
)


def _changed_enum_fields(before: list[dict], after: list[dict]) -> list[tuple[str, str]]:
    """返回枚举值域发生变化的字段 [(字段名, 首个差异示例)]。"""
    out = []
    for old, new in zip(before, after):
        old_values = old.get("enum_values") or []
        new_values = new.get("enum_values") or []
        if old_values == new_values:
            continue
        sample = ""
        for a, b in zip(old_values, new_values):
            if a != b:
                sample = f"{a} → {b}"
                break
        out.append((str(old.get("name")), sample))
    return out


def main():
    parser = argparse.ArgumentParser(
        description="用 ARFF 同步数据集字段样例值与枚举值域"
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印差异，不写库")
    args = parser.parse_args()

    with SessionLocal() as db:
        datasets = db.query(Dataset).order_by(Dataset.id).all()
        updated, skipped = 0, 0
        for d in datasets:
            path = resolve_dataset_path(d.file_path)
            if not os.path.exists(path):
                print(f"  [skip] {d.logical_id}: 文件不存在 {path}")
                skipped += 1
                continue
            try:
                new_fields, _ = read_arff(path, max_rows=50)  # 前 50 行足够取样例
            except Exception as exc:  # noqa: BLE001
                print(f"  [error] {d.logical_id}: {exc}")
                skipped += 1
                continue

            before = d.fields_schema or []
            merged = sync_enum_values(enrich_sample_values(before, new_fields), new_fields)
            if merged == before:
                print(f"  [same] {d.logical_id}: 无变化")
                continue

            enum_changed = _changed_enum_fields(before, merged)
            print(
                f"  [{'dry' if args.dry_run else 'ok'}] {d.logical_id}: 同步 {len(merged)} 个字段，"
                f"其中枚举值域变化 {len(enum_changed)} 个"
            )
            for name, sample in enum_changed[:2]:
                print(f"        {name}: {sample}")
            if not args.dry_run:
                d.fields_schema = merged
                db.add(d)
            updated += 1

        if args.dry_run:
            print(f"\n[dry-run] 将更新 {updated} 个，跳过 {skipped} 个（未写库）")
        else:
            db.commit()
            print(f"\n完成：更新 {updated} 个，跳过 {skipped} 个")


if __name__ == "__main__":
    main()
