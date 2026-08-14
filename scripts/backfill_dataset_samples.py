"""backfill_dataset_samples.py — 为已登记数据集回填字段样例值（V3.0 §3.1.4）。

已有数据集在旧版 seed 注册时 fields_schema 没有 sample_values；
本脚本复用 backend/app/utils/arff_reader.py 重新解析 data/ 下的 ARFF，
按字段名对齐合并 sample_values，幂等（重复执行结果一致）。

用法（项目根目录）：
    python scripts/backfill_dataset_samples.py
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

from app.db import SessionLocal  # noqa: E402
from app.models.dataset import Dataset  # noqa: E402
from app.services.training_executor import resolve_dataset_path  # noqa: E402
from app.utils.arff_reader import read_arff, enrich_sample_values  # noqa: E402


def main():
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
            merged = enrich_sample_values(d.fields_schema, new_fields)
            # 只有真正变化才写库
            if merged != d.fields_schema:
                d.fields_schema = merged
                db.add(d)
                updated += 1
                print(f"  [ok] {d.logical_id}: 补 {len(merged)} 个字段的样例值")
            else:
                print(f"  [same] {d.logical_id}: 无变化")
        db.commit()
        print(f"\n完成：更新 {updated} 个，跳过 {skipped} 个")


if __name__ == "__main__":
    main()
