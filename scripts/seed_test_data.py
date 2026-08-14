#!/usr/bin/env python
"""数据库测试数据初始化脚本（seed_test_data.py）

把老师提供的 ARFF 数据集注册进 PostgreSQL 的 dataset 表（metadata：字段结构、
标签字段、文件路径），并创建测试账号、配置每个场景的风险阈值。全部走 Service 层，
顺带验证整条「Service → ORM → PostgreSQL」链路。

用法：
    python scripts/seed_test_data.py                          # 默认从微信下载目录读 ARFF
    python scripts/seed_test_data.py --source D:/some/dir     # 指定 ARFF 所在目录
    python scripts/seed_test_data.py --skip-copy              # ARFF 已在 data/ 下，只注册 DB

重复运行安全：用户/数据集/阈值已存在则跳过，不产生重复版本。

注册成功后如何验证（配合后端启动）：
    - 启动后端：cd backend && python -m app.main
    - 打开 Swagger：http://localhost:12312/docs
    - 请求头带 X-User-Id: 1（admin），即可测试 /api/v1/datasets 等接口
"""
import argparse
import os
import re
import shutil
import stat
import sys

# ---------------------------------------------------------------------------
# 路径与依赖
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

# GBK 控制台打印特殊字符(如 ﻿)会 UnicodeEncodeError,统一转 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 默认源目录：老师微信下载目录（可在命令行用 --source 覆盖）
DEFAULT_SOURCE = (
    r"D:\001Mine\008NoSpace\007WeChat\xwechat_files"
    r"\wxid_zdxsh4dko92212_faac\msg\file\2026-07"
)

# 8 个数据集：logical_id -> 源文件名 / 场景编码 / 标签字段 / 是否二分类
DATASETS = {
    "dis_raw_data": {
        "file": "DIS_raw_data(1).arff",
        "scenario": "geological_risk",
        "label": "Label",
        "binary": True,
    },
    "dis_landslides": {
        "file": "DIS_Landslides(1).arff",
        "scenario": "geological_risk",
        "label": "LS",
        "binary": True,
    },
    "dis_causative_factors": {
        "file": "DIS_Landslide_Causative_Factors(1).arff",
        "scenario": "geological_risk",
        "label": "landslides",  # 数值标签，>0 即风险（DATASET_RISK_GT_ZERO）
        "binary": True,
    },
    "dis_global_catalog": {
        "file": "DIS_Global_Landslide_Catalog_Export(1).arff",
        "scenario": "geological_risk",
        "label": "landslide_size",  # 多分类编目数据，不参与二分类训练
        "binary": False,
    },
    "dis_guaruja_random": {
        "file": "DIS_guaruja_random(1).arff",
        "scenario": "geological_risk",
        "label": "class",
        "binary": True,
    },
    "carrier_feature2_biaoqian": {
        "file": "Feature2_Cleaning_biaoqian(1).arff",
        "scenario": "flightdeck_operation",
        "label": "Collision",
        "binary": True,
    },
    "carrier_feature2_lisan": {
        "file": "Feature2_Cleaning_lisan(1).arff",
        "scenario": "flightdeck_operation",
        "label": "Collision",
        "binary": True,
    },
    "carrier_paired_trail": {
        "file": "paired_TrailData_feature2_biaoqian(1).arff",
        "scenario": "flightdeck_operation",
        "label": "Collision",
        "binary": True,
    },
    # 补录：网络 / 电力场景真实数据集（原文件在下载目录，source 指向原始文件）
    "nf_unsw_nb15": {
        "file": "NF-UNSW-NB15-v2.arff",
        "source": r"D:\001Mine\005   Download\NF-UNSW-NB15-v20503",
        "scenario": "network_security",
        "label": "Label",
        "binary": True,
    },
    "kdd_train_20": {
        "file": "KDDTrain_20Percent.arff",
        "source": r"D:\001Mine\005   Download\KDDTrain+_20Percent0503",
        "scenario": "network_security",
        "label": "class",
        "binary": True,
    },
    "powergrid_knowledge": {
        "file": "powergrid_knowledgebase_dataset.arff",
        "source": r"D:\001Mine\005   Download\powergrid_knowledgebase_dataset0503",
        "scenario": "power_system",
        "label": "Target_Event",
        "binary": True,
    },
}

# 目标子目录（data/ 已被 gitignore，大文件不进版本库）
SCENARIO_DIR = {
    "network_security": "network",
    "power_system": "power",
    "geological_risk": "geological",
    "flightdeck_operation": "carrier",
}

# 阈值兜底（每个场景配置一套）
THRESHOLDS = [(0.5, 0.8)]  # (medium, high)

# 测试账号：(username, password, role)
TEST_USERS = [
    ("admin", "admin123", "ADMIN"),
    ("alice", "alice123", "USER"),
]


# ---------------------------------------------------------------------------
# ARFF 解析
# ---------------------------------------------------------------------------
_ATTR_RE = re.compile(r"@ATTRIBUTE\s+(.+)$", re.IGNORECASE)


def _split_arff_values(content: str):
    """按逗号切分 {..} 内的枚举值，正确处理引号与 \\' 转义。"""
    vals, cur, in_q = [], [], False
    i = 0
    while i < len(content):
        ch = content[i]
        if ch == "\\" and i + 1 < len(content) and content[i + 1] == "'":
            cur.append("'")
            i += 2
            continue
        if ch == "'":
            in_q = not in_q
            i += 1
            continue
        if ch == "," and not in_q:
            vals.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if cur:
        vals.append("".join(cur).strip())
    return [v.strip("'") for v in vals if v.strip()]


def parse_arff_fields(path: str, label_field: str):
    """解析 ARFF，返回 (fields_schema, rows)。rows 为 @data 后非空行数。"""
    fields, rows, in_data = [], 0, False
    for raw in open(path, encoding="utf-8-sig", errors="replace"):
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("@ATTRIBUTE"):
            body = line[len("@ATTRIBUTE"):].strip()
            m = _ATTR_RE.match(line)
            if not m:
                continue
            body = m.group(1).strip()
            if body.startswith("'") or body.startswith('"'):
                # 带引号字段名：@attribute 'name' type
                name, _, typ = body[1:].partition(body[0])
                typ = typ.strip()
            else:
                parts = body.split(None, 1)
                if len(parts) != 2:
                    continue
                name, typ = parts[0], parts[1].strip()
            name = name.lstrip("\ufeff").strip()
            if typ.lower().startswith("{"):
                enum_values = _split_arff_values(typ.strip("{}"))
                field_type = "enum"
            else:
                enum_values = []
                field_type = typ.lower().split()[0] if typ.lower().split()[0] in ("numeric", "string", "date", "real", "integer") else "numeric"
            fields.append({
                "name": name,
                "type": field_type,
                "role": "label" if name == label_field else "feature",
                "enum_values": enum_values,
                "sample_values": [],
            })
        elif upper.startswith("@DATA"):
            in_data = True
        elif in_data and line and not line.startswith("%") and not line.startswith("@"):
            rows += 1
            values = [v.strip().strip("'\"") for v in line.split(",")]
            for i, v in enumerate(values):
                if i >= len(fields):
                    break
                if len(fields[i]["sample_values"]) >= 2:
                    continue
                if v and v != "?" and v not in fields[i]["sample_values"]:
                    fields[i]["sample_values"].append(v)
    return fields, rows


# ---------------------------------------------------------------------------
# 数据库写入（走 Service 层）
# ---------------------------------------------------------------------------
def get_or_create_admin(svc_user, db):
    from sqlalchemy import select
    from app.models.app_user import AppUser

    admin = db.scalar(select(AppUser).where(AppUser.username == "admin"))
    if admin:
        return admin

    class _Bootstrap:
        id = 0
        role = "ADMIN"
        status = "ENABLED"

    resp = svc_user.create(
        current_user=_Bootstrap(), username="admin", password="admin123", role="ADMIN"
    )
    print(f"  [user] admin 创建 -> code={resp.code} msg={resp.message}")
    return db.scalar(select(AppUser).where(AppUser.username == "admin"))


def ensure_user(svc_user, db, username, password, role):
    from sqlalchemy import select
    from app.models.app_user import AppUser

    exists = db.scalar(select(AppUser).where(AppUser.username == username))
    if exists:
        print(f"  [user] {username} 已存在，跳过")
        return
    admin = get_or_create_admin(svc_user, db)
    resp = svc_user.create(
        current_user=admin, username=username, password=password, role=role
    )
    print(f"  [user] {username}({role}) 创建 -> code={resp.code}")


def ensure_thresholds(svc_threshold, db, admin, scenario_map):
    from app.models.risk_threshold import RiskThreshold

    for code, _sc_id in scenario_map.items():
        for medium, high in THRESHOLDS:
            threshold = db.get(RiskThreshold, _sc_id)
            if threshold:
                print(f"  [threshold] 场景 {code} 已配置，跳过")
                continue
            resp = svc_threshold.update(
                current_user=admin, scenario_id=_sc_id,
                medium_threshold=medium, high_threshold=high,
            )
            print(f"  [threshold] 场景 {code} 配置 medium={medium} high={high} -> code={resp.code}")


def register_dataset(svc_dataset, db, admin, logical_id, cfg, scenario_map, source_dir, skip_copy):
    from sqlalchemy import select
    from app.models.dataset import Dataset

    exists = db.scalar(
        select(Dataset).where(Dataset.logical_id == logical_id)
    )
    if exists:
        print(f"  [dataset] {logical_id} 已存在（version={exists.version}），跳过")
        return

    # 优先用 per-dataset 的 source（自定义源文件），否则用默认源目录 + 文件名
    src_path = cfg.get("source") or os.path.join(source_dir, cfg["file"])
    if not os.path.exists(src_path):
        print(f"  [dataset] {logical_id}: 找不到源文件 {src_path}，跳过")
        return

    subdir = SCENARIO_DIR[cfg["scenario"]]
    clean_name = cfg["file"].split("(")[0].strip() + ".arff"
    if clean_name.endswith(".arff.arff"):
        clean_name = clean_name.replace(".arff.arff", ".arff")
    dest_dir = os.path.join(PROJECT_ROOT, "data", subdir)
    dest_path = os.path.join(dest_dir, clean_name)

    if not skip_copy:
        os.makedirs(dest_dir, exist_ok=True)
        # 微信下载的文件是只读,用 copy(不复制权限位)并在覆盖前清只读
        if os.path.exists(dest_path):
            os.chmod(dest_path, stat.S_IWRITE)
        shutil.copy(src_path, dest_path)
        os.chmod(dest_path, stat.S_IWRITE)
        print(f"  [copy] {cfg['file']} -> data/{subdir}/{clean_name}")

    fields, rows = parse_arff_fields(dest_path, cfg["label"])
    label_role = [f for f in fields if f["role"] == "label"]
    if not label_role:
        print(f"  [dataset] {logical_id}: 标签字段 {cfg['label']} 不在 ARFF 中，跳过")
        return

    resp = svc_dataset.create(
        current_user=admin,
        logical_id=logical_id,
        scenario_id=scenario_map[cfg["scenario"]],
        file_path=os.path.join("data", subdir, clean_name),
        fields_schema=fields,
        label_field=cfg["label"],
    )
    note = "（多分类，不参与二分类训练）" if not cfg["binary"] else ""
    print(
        f"  [dataset] {logical_id} 注册 -> code={resp.code} "
        f"rows={rows} label={cfg['label']} fields={len(fields)} {note}"
    )
    if resp.code != 0:
        print(f"      ! 失败原因: {resp.message}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="数据库测试数据初始化")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="ARFF 源目录")
    parser.add_argument("--skip-copy", action="store_true", help="文件已在 data/ 下，只注册 DB")
    args = parser.parse_args()

    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models.scenario import Scenario
    from app.services.dataset_service import DatasetService
    from app.services.risk_threshold_service import RiskThresholdService
    from app.services.user_service import UserService

    print("=" * 64)
    print("数据库测试数据初始化开始")
    print("=" * 64)

    with SessionLocal() as db:
        svc_user = UserService(db)
        svc_dataset = DatasetService(db)
        svc_threshold = RiskThresholdService(db)

        # 1. 测试账号
        print("\n[1/3] 测试账号")
        for username, password, role in TEST_USERS:
            ensure_user(svc_user, db, username, password, role)
        admin = get_or_create_admin(svc_user, db)

        # 2. 场景映射（按编码查库，不写死 id）
        scenario_map = {}
        for code in SCENARIO_DIR:
            sc = db.scalar(select(Scenario).where(Scenario.code == code))
            if sc:
                scenario_map[code] = sc.id
            else:
                print(f"  ! 场景 {code} 不存在于数据库，相关数据集将跳过")
        if not scenario_map:
            print("  数据库没有任何目标场景，请先执行 alembic upgrade head 初始化场景种子数据")
            return

        # 3. 数据集注册
        print("\n[2/3] 数据集注册")
        for logical_id, cfg in DATASETS.items():
            if cfg["scenario"] not in scenario_map:
                print(f"  [dataset] {logical_id}: 场景 {cfg['scenario']} 缺失，跳过")
                continue
            register_dataset(svc_dataset, db, admin, logical_id, cfg, scenario_map, args.source, args.skip_copy)

        # 4. 风险阈值
        print("\n[3/3] 风险阈值")
        ensure_thresholds(svc_threshold, db, admin, scenario_map)

        # 5. 汇总
        print("\n" + "=" * 64)
        print("汇总（数据库实际状态）")
        print("=" * 64)
        from app.models.dataset import Dataset
        from sqlalchemy import func
        for code, sc_id in scenario_map.items():
            n_ds = db.scalar(
                select(func.count()).select_from(Dataset).where(Dataset.scenario_id == sc_id)
            )
            sc = db.get(Scenario, sc_id)
            print(f"  场景 {sc.name if sc else code} ({code}): {n_ds} 个数据集")

        print("\n✅ 初始化完成。启动后端后到 http://localhost:12312/docs 测试（请求头 X-User-Id: 1）")


if __name__ == "__main__":
    main()
