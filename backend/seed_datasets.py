"""将 data/ 目录下已有数据文件注册到数据库。

用法：
    cd backend && python seed_datasets.py
"""
import os
import sys
import re
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import Base, engine, SessionLocal
from app import models  # noqa: register all tables
from app.models.dataset import Dataset
from app.models.scenario import Scenario
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

DATASETS = [
    {
        "scenario_code": "network_security",
        "logical_id": "kdd_train_20_percent",
        "file_path": "data/nf_unsw/KDDTrain+_20Percent0503",
        "label_field": "class",
        "parser": "arff",
    },
    {
        "scenario_code": "power_system",
        "logical_id": "power_sample",
        "file_path": "data/power_data/sample_demo.csv",
        "label_field": "risk_level",
        "parser": "csv",
    },
    {
        "scenario_code": "flightdeck_operation",
        "logical_id": "carrier_sample",
        "file_path": "data/carrier_sim/sample_demo.csv",
        "label_field": "risk_level",
        "parser": "csv",
    },
]


def parse_arff_fields(path: Path) -> list[dict]:
    """从 ARFF 文件头解析字段定义。"""
    fields = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.lower().startswith("@data"):
                break
            m = re.match(r"@attribute\s+(\S+)\s+(.+)", line, re.IGNORECASE)
            if not m:
                continue
            name, type_str = m.group(1), m.group(2).strip()
            # 判断类型
            enum_match = re.match(r"\{(.+)\}", type_str)
            if enum_match:
                values = [v.strip() for v in enum_match.group(1).split(",")]
                role = "label" if name == "class" else "feature"
                fields.append({
                    "name": name, "type": "enum",
                    "role": role, "enum_values": values,
                })
            elif type_str.lower() == "numeric":
                role = "label" if name == "class" else "feature"
                fields.append({
                    "name": name, "type": "float",
                    "role": role,
                })
            else:
                fields.append({
                    "name": name, "type": "string",
                    "role": "feature",
                })
    return fields


def parse_csv_fields(path: Path) -> list[dict]:
    """从 CSV 首行解析字段定义。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().strip()
    names = [h.strip() for h in header.split(",")]
    fields = []
    for n in names:
        role = "label" if n == "risk_level" else "feature"
        fields.append({"name": n, "type": "float" if n != "risk_level" else "enum", "role": role})
    return fields


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        for ds_def in DATASETS:
            # 查找场景 ID
            scenario = db.scalar(
                select(Scenario).where(Scenario.code == ds_def["scenario_code"])
            )
            if scenario is None:
                print(f"  WARN: scenario {ds_def['scenario_code']} not found, skip")
                continue

            # 检查是否已存在
            existing = db.scalar(
                select(Dataset).where(
                    Dataset.logical_id == ds_def["logical_id"],
                    Dataset.version == 1,
                )
            )
            if existing is not None:
                print(f"  SKIP: {ds_def['logical_id']} v1 already exists")
                continue

            # 解析字段
            file_path = PROJECT_ROOT / ds_def["file_path"]
            if not file_path.exists():
                print(f"  WARN: file not found {file_path}, skip")
                continue

            if ds_def["parser"] == "arff":
                fields_schema = parse_arff_fields(file_path)
            else:
                fields_schema = parse_csv_fields(file_path)

            dataset = Dataset(
                logical_id=ds_def["logical_id"],
                version=1,
                scenario_id=scenario.id,
                file_path=ds_def["file_path"],
                fields_schema=fields_schema,
                label_field=ds_def["label_field"],
                uploaded_by=1,  # admin
                uploaded_at=now,
                status="ACTIVE",
            )
            db.add(dataset)
            db.commit()
            print(f"  OK: {ds_def['logical_id']} v1 - {len(fields_schema)} fields")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Dataset Seed ===")
    seed()
    print("Done.")
