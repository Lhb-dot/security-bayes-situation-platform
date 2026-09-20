#!/usr/bin/env python
"""虚拟生产数据注入（scripts/seed_production_data.py）

给安全贝叶斯态势感知平台灌一批接近生产规模的数据，用于端到端功能检验。

数据链路（每一步都走真实 HTTP 接口 → Service → ORM → PostgreSQL，不直插数据库）：

    账号（4 场景 × 管理员 + 4 用户）
      → 数据集（三级可见性：platform / company / personal）
      → 模型（各场景管理员真实训练 → 发布 → 设默认推荐）
      → 推理记录 + 风险事件（真实 Java 预测服务）
      → 处置记录（状态流转 + 处置说明）
      → 态势快照 + 态势报告
      → 时间轴铺开（把「都是刚刚」改成近 60 天的分布）

用法：
    python scripts/seed_production_data.py --stage accounts,datasets,models
    python scripts/seed_production_data.py --stage inference --inferences 2000
    python scripts/seed_production_data.py --stage handling,reports
    python scripts/seed_production_data.py --stage timeline
    python scripts/seed_production_data.py --all

重跑安全性（实测确认）：
    账号 / 数据集 / 模型 —— 跳过已存在的，重复跑不新增；
    处置 —— 只挑 PENDING 事件，天然收敛；
    推理 / 报告 / 快照 —— **追加式**，重跑会再生成一批（要重跑先清库）。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("WB_BASE", "http://127.0.0.1:12312/api/v1")
PASSWORD = "123456"
REPORT_PATH = PROJECT_ROOT / "tmp" / "seed_production_report.json"

# ---------------------------------------------------------------------------
# 账号与场景配置
# ---------------------------------------------------------------------------
# 每个场景：1 个场景管理员 + 4 个场景用户（含已有的 alice / bob / carol）。
# 阈值刻意各不相同 —— 同一份 risk_score，不同账号看到的风险等级不同，
# 这是「账号级风险视图」这条口径能被验证的前提。
SCENARIOS = [
    {
        "code": "network_security",
        "id": 1,
        "admin": "net_admin",
        "users": ["alice", "net_user01", "net_user02", "net_user03"],
        "train": [("nf_unsw_nb15_v2", ["A2WNB", "MAWNB"])],
        "infer": ["nf_unsw_nb15_v2", "kdd_train_20_percent"],
        "company": ("net_flow_company_v1", "data/network/NF-UNSW-NB15-v2.arff", "Label"),
        "personal": ("alice_conn_personal_v1", "data/network/KDDTrain_20Percent.arff", "class", "alice"),
        "thresholds": [(0.50, 0.80), (0.45, 0.75), (0.55, 0.85), (0.35, 0.65), (0.60, 0.90)],
    },
    {
        "code": "power_system",
        "id": 2,
        "admin": "power_admin",
        "users": ["bob", "power_user01", "power_user02", "power_user03"],
        "train": [("powergrid_knowledgebase", ["A2WNB", "MAWNB", "PMWNB", "DIWNB"])],
        "infer": ["powergrid_knowledgebase"],
        "company": ("power_grid_company_v1", "data/power/powergrid_knowledgebase_dataset.arff", "Target_Event"),
        "personal": ("bob_sensor_personal_v1", "data/power/powergrid_knowledgebase_dataset.arff", "Target_Event", "bob"),
        "thresholds": [(0.50, 0.80), (0.40, 0.70), (0.55, 0.85), (0.30, 0.60), (0.65, 0.90)],
    },
    {
        "code": "flightdeck_operation",
        "id": 3,
        "admin": "zs",
        "users": ["deck_user01", "deck_user02", "deck_user03", "deck_user04"],
        "train": [("carrier_feature2_biaoqian", ["A2WNB", "MAWNB"])],
        "infer": ["carrier_feature2_biaoqian"],
        "company": ("carrier_track_company_v1", "data/carrier/Feature2_Cleaning_lisan.arff", "Collision"),
        "personal": ("deck_user01_trail_personal_v1", "data/carrier/paired_TrailData_feature2_biaoqian.arff", "Collision", "deck_user01"),
        "thresholds": [(0.50, 0.80), (0.45, 0.70), (0.55, 0.85), (0.35, 0.65), (0.60, 0.88)],
    },
    {
        "code": "geological_risk",
        "id": 4,
        "admin": "geo_admin",
        "users": ["carol", "geo_user01", "geo_user02", "geo_user03"],
        "train": [("dis_raw_data", ["A2WNB", "MAWNB", "PMWNB", "DIWNB"])],
        "infer": ["dis_raw_data", "dis_landslides", "dis_guaruja_random"],
        "company": ("geo_slope_company_v1", "data/geological/DIS_Landslides.arff", "LS"),
        "personal": ("carol_slope_personal_v1", "data/geological/DIS_raw_data.arff", "Label", "carol"),
        "thresholds": [(0.50, 0.80), (0.42, 0.72), (0.55, 0.85), (0.38, 0.68), (0.62, 0.90)],
    },
]

SUPER_ADMIN = "admin"

#: 推理条数（按角色分配；--inferences 会整体缩放）
INFERENCE_PLAN = {"super_admin": 150, "scenario_admin": 120, "scenario_user": 85}


# ---------------------------------------------------------------------------
# HTTP 客户端（登录 → 带 CSRF 的写请求）
# ---------------------------------------------------------------------------
class Client:
    """一个账号一个会话。写操作自动带 X-CSRF-Token。"""

    def __init__(self, username: str, password: str = PASSWORD):
        self.username = username
        self.s = requests.Session()
        self.s.trust_env = False  # 绕开系统代理，否则本机端口会拿到代理的 502
        r = self.s.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=60)
        r.raise_for_status()
        body = r.json()
        if body.get("code") != 0:
            raise RuntimeError(f"{username} 登录失败: {body}")
        self.user = body["data"]["user"]
        self.s.headers["X-CSRF-Token"] = body["data"]["csrf_token"]

    def call(self, method: str, path: str, **kw):
        kw.setdefault("timeout", 300)
        r = self.s.request(method, f"{BASE}{path}", **kw)
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = {"_raw": r.text[:400]}
        return r.status_code, body

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, **kw):
        return self.call("POST", path, **kw)

    def put(self, path, **kw):
        return self.call("PUT", path, **kw)

    def delete(self, path, **kw):
        return self.call("DELETE", path, **kw)

    def data(self, method, path, **kw):
        """调用并返回 data 字段；非 0 code 直接抛错。"""
        st, body = self.call(method, path, **kw)
        if body.get("code") != 0:
            raise RuntimeError(f"{self.username} {method} {path} -> {st} {body.get('message') or body}")
        return body.get("data")


# ---------------------------------------------------------------------------
# 阶段一：账号 + 阈值
# ---------------------------------------------------------------------------
def stage_accounts(state):
    admin = Client(SUPER_ADMIN)
    created, skipped = [], []

    def ensure(username, role, scenario_id):
        st, body = admin.post("/users", json={
            "username": username, "password": PASSWORD,
            "role": role, "scenario_id": scenario_id,
        })
        if body.get("code") == 0:
            created.append(username)
        elif "已存在" in str(body.get("message", "")):
            skipped.append(username)
        else:
            print(f"  ! 创建 {username} 失败: {st} {body.get('message')}")

    for sc in SCENARIOS:
        ensure(sc["admin"], "SCENARIO_ADMIN", sc["id"])
        for user in sc["users"]:
            ensure(user, "SCENARIO_USER", sc["id"])

    print(f"  账号：新建 {len(created)}，已存在 {len(skipped)}")
    state["accounts_created"] = created

    # 阈值：每个账号在自己场景配一套（超管四个场景都配）
    threshold_writes = 0
    for sc in SCENARIOS:
        pairs = sc["thresholds"]
        members = [sc["admin"]] + sc["users"]
        for name, pair in zip(members, pairs):
            cli = Client(name)
            st, body = cli.put(f"/risk-thresholds/{sc['id']}",
                               json={"medium_threshold": pair[0], "high_threshold": pair[1]})
            if body.get("code") == 0:
                threshold_writes += 1
            else:
                print(f"  ! 阈值 {name}/{sc['code']} 失败: {body.get('message')}")
    for sc in SCENARIOS:
        admin.put(f"/risk-thresholds/{sc['id']}", json={"medium_threshold": 0.50, "high_threshold": 0.80})
    print(f"  阈值：写入 {threshold_writes} 条账号级阈值（超管 4 个场景各 0.50/0.80）")
    state["threshold_writes"] = threshold_writes
    return state


# ---------------------------------------------------------------------------
# 阶段二：数据集（三级可见性）
# ---------------------------------------------------------------------------
def stage_datasets(state):
    """上传 company / personal 数据集。

    幂等：先按上传者视角查一遍已有 logical_id，已存在就跳过。
    —— 平台的 `/datasets/upload` 对同一 logical_id 是「新增一个版本」，
    不做这层判断的话重跑会给每个数据集多出一个 v2（实测 19 → 27 条）。
    """
    uploaded, skipped = [], []

    def have(cli):
        items = cli.data("GET", "/datasets", params={"page": 1, "page_size": 200})["items"]
        return {d["logical_id"] for d in items}

    for sc in SCENARIOS:
        # company：场景管理员上传
        logical_id, rel_src, label = sc["company"]
        cli = Client(sc["admin"])
        if logical_id in have(cli):
            skipped.append(logical_id)
            print(f"  [company] {logical_id} 跳过（已存在）")
        else:
            st, body = cli.post("/datasets/upload", data={
                "logical_id": logical_id, "scenario_id": str(sc["id"]),
                "label_field": label, "visibility": "company",
            }, files={"file": (Path(rel_src).name, (PROJECT_ROOT / rel_src).read_bytes(), "application/octet-stream")})
            if body.get("code") == 0:
                uploaded.append({"logical_id": logical_id, "visibility": "company", "by": sc["admin"]})
                print(f"  [company] {logical_id} <- {sc['admin']}")
            else:
                print(f"  [company] {logical_id} 跳过/失败: {body.get('message')}")

        # personal：场景用户上传（强制 personal）
        logical_id, rel_src, label, owner = sc["personal"]
        cli = Client(owner)
        if logical_id in have(cli):
            skipped.append(logical_id)
            print(f"  [personal] {logical_id} 跳过（已存在）")
        else:
            st, body = cli.post("/datasets/upload", data={
                "logical_id": logical_id, "scenario_id": str(sc["id"]), "label_field": label,
            }, files={"file": (Path(rel_src).name, (PROJECT_ROOT / rel_src).read_bytes(), "application/octet-stream")})
            if body.get("code") == 0:
                uploaded.append({"logical_id": logical_id, "visibility": "personal", "by": owner})
                print(f"  [personal] {logical_id} <- {owner}")
            else:
                print(f"  [personal] {logical_id} 跳过/失败: {body.get('message')}")

    state["datasets_uploaded"] = uploaded
    state["datasets_skipped"] = skipped
    return state


# ---------------------------------------------------------------------------
# 阶段三：模型（训练 → 发布 → 默认推荐）
# ---------------------------------------------------------------------------
def _param_variants(schema, index):
    """按算法注册的 param_schema 造一组合法训练参数。

    取 schema 默认值作为基线，再按 index 轮换离散化方式 / 分箱数，
    使同一数据集上的多个算法版本参数不同（模型对比才有内容可看）。
    """
    params = {}
    for item in schema or []:
        if item.get("default") is not None:
            params[item["name"]] = item["default"]
    if "discrete_method" in params:
        params["discrete_method"] = ("equal_width", "equal_freq")[index % 2]
    if "discrete_bins" in params:
        params["discrete_bins"] = (5, 10, 20)[index % 3]
    return params


def stage_models(state):
    admin = Client(SUPER_ADMIN)
    algorithm_list = admin.data("GET", "/algorithms")
    algorithms = {a["code"]: a for a in algorithm_list}
    datasets = {d["logical_id"]: d for d in admin.data("GET", "/datasets", params={"page": 1, "page_size": 200})["items"]}
    trained, published, defaults, failed = [], [], [], []

    for sc in SCENARIOS:
        cli = Client(sc["admin"])
        existing = cli.data("GET", "/model-versions", params={"page": 1, "page_size": 200})["items"]
        have = {(m["dataset_logical_id"], m["algorithm_code"]) for m in existing}
        for logical_id, algo_codes in sc["train"]:
            dataset = datasets.get(logical_id)
            if dataset is None:
                print(f"  ! 数据集 {logical_id} 不存在，跳过训练")
                continue
            for index, code in enumerate(algo_codes):
                if (logical_id, code) in have:
                    continue
                algorithm = algorithms.get(code)
                if algorithm is None:
                    continue
                params = _param_variants(algorithm.get("param_schema"), index)
                t0 = time.perf_counter()
                try:
                    res = cli.data("POST", "/model-versions/train", json={
                        "scenario_id": sc["id"], "dataset_id": dataset["id"],
                        "algorithm_id": algorithm["id"], "training_parameters": params,
                    })
                except RuntimeError as exc:
                    failed.append({"dataset": logical_id, "algorithm": code, "error": str(exc)})
                    print(f"  ! 训练 {logical_id}/{code} 失败: {exc}")
                    continue
                mid = res["id"]
                trained.append({"id": mid, "dataset": logical_id, "algorithm": code,
                                "by": sc["admin"], "params": params,
                                "seconds": round(time.perf_counter() - t0, 1)})
                cli.data("POST", f"/model-versions/{mid}/publish")
                published.append(mid)
                print(f"  [train] {sc['code']:22s} {logical_id:28s} {code:6s} "
                      f"id={mid} acc={res['evaluation_metrics'].get('accuracy')} "
                      f"{params} ({round(time.perf_counter() - t0, 1)}s) → PUBLISHED")

        # 默认推荐：每个 (场景, 数据集) 一个
        for logical_id, _ in sc["train"]:
            dataset = datasets.get(logical_id)
            if dataset is None:
                continue
            models = cli.data("GET", "/model-versions", params={
                "page": 1, "page_size": 200, "dataset_id": dataset["id"]})["items"]
            pub = [m for m in models if m["status"] == "PUBLISHED"]
            if not pub or any(m["is_default"] for m in pub):
                continue
            best = max(pub, key=lambda m: (m.get("evaluation_metrics") or {}).get("accuracy") or 0)
            cli.data("POST", f"/model-versions/{best['id']}/set-default")
            defaults.append(best["id"])
            print(f"  [default] {logical_id} -> #{best['id']} {best['algorithm_code']}")

    print(f"  模型：训练 {len(trained)} 个，发布 {len(published)} 个，"
          f"默认推荐 {len(defaults)} 个，失败 {len(failed)} 个")
    state["models_trained"] = trained
    state["models_published"] = published
    state["models_default"] = defaults
    state["models_failed"] = failed
    return state


# ---------------------------------------------------------------------------
# 阶段四：推理记录 + 风险事件
# ---------------------------------------------------------------------------
def _clean(value: str) -> str:
    return str(value).strip().strip("'\" \t\r\n")


def load_pool(dataset):
    """读取数据集 ARFF，返回 (字段名列表, 正类行, 负类行)。

    正负类按 constants.is_risk_label 的显式映射判定（与平台口径一致，不自动推断）。
    必须整份读：NF-UNSW-NB15-v2 的前 6000 行全是负类，只读头部会得到空的正类池。
    """
    from app.services.constants import is_risk_label
    from app.utils.arff_reader import read_arff

    path = PROJECT_ROOT / str(dataset["file_path"]).replace("\\", "/")
    fields, rows = read_arff(str(path), max_rows=None)
    names = [f["name"] for f in fields]
    schema_names = [f["name"] for f in dataset["fields_schema"]]
    if names != schema_names:
        raise RuntimeError(f"{dataset['logical_id']}: ARFF 字段与库内 fields_schema 不一致")
    label_index = names.index(dataset["label_field"])
    pos, neg = [], []
    for row in rows:
        if len(row) < len(names):
            continue
        (pos if is_risk_label(dataset["logical_id"], _clean(row[label_index])) else neg).append(row)
    return names, pos, neg


def build_features(names, label_field, row):
    return {name: _clean(row[i]) for i, name in enumerate(names) if name != label_field}


def stage_inference(state, total_hint, only_accounts=None):
    admin = Client(SUPER_ADMIN)
    datasets = {d["logical_id"]: d for d in admin.data("GET", "/datasets", params={"page": 1, "page_size": 200})["items"]}

    # 可用模型按**各场景管理员的视角**取：
    # 超管的 /model-versions 只返回「自己训练的」模型（ModelVersionService.get_list），
    # 场景管理员训练的模型对它不可见，所以要逐场景去问各自的场景管理员。
    by_scenario = {}
    for sc in SCENARIOS:
        items = Client(sc["admin"]).data("GET", "/model-versions",
                                         params={"page": 1, "page_size": 200, "status": "PUBLISHED"})["items"]
        by_scenario[sc["id"]] = [m for m in items if m["status"] == "PUBLISHED"]
        print(f"    {sc['code']:22s} 已发布模型 {len(by_scenario[sc['id']])} 个 "
              f"（{[m['algorithm_code'] for m in by_scenario[sc['id']]]}）")

    print("  采样池：")
    pools = {}
    for sc in SCENARIOS:
        for logical_id in sc["infer"]:
            ds = datasets.get(logical_id)
            if ds is None or logical_id in pools:
                continue
            names, pos, neg = load_pool(ds)
            pools[logical_id] = (names, pos, neg)
            print(f"    {logical_id:30s} 正类 {len(pos):5d} / 负类 {len(neg):5d}")

    # 每个账号的推理条数
    plan = []
    scale = total_hint / sum(
        INFERENCE_PLAN["scenario_admin"] + len(sc["users"]) * INFERENCE_PLAN["scenario_user"]
        for sc in SCENARIOS
    ) if total_hint else 1.0
    plan.append((SUPER_ADMIN, "super_admin", int(INFERENCE_PLAN["super_admin"] * scale), None))
    for sc in SCENARIOS:
        plan.append((sc["admin"], "scenario_admin", int(INFERENCE_PLAN["scenario_admin"] * scale), sc["id"]))
        for u in sc["users"]:
            plan.append((u, "scenario_user", int(INFERENCE_PLAN["scenario_user"] * scale), sc["id"]))
    if only_accounts:
        wanted = {a.strip() for a in only_accounts}
        plan = [p for p in plan if p[0] in wanted]
        print(f"  仅处理指定账号：{sorted(wanted)}")

    results = {"ok": 0, "risk": 0, "fail": 0, "errors": [], "per_account": {}}

    def run_account(username, role, count, scenario_id):
        cli = Client(username)
        combos = []
        if scenario_id is None:
            for sid, items in by_scenario.items():
                combos.extend(items)
        else:
            combos = list(by_scenario.get(scenario_id, []))
        if not combos:
            return username, 0, 0, 0, ["无可用已发布模型"]
        rng = random.Random(f"{username}-seed")
        ok = risk = fail = 0
        errs = []
        for _ in range(count):
            model = rng.choice(combos)
            logical_id = model["dataset_logical_id"]
            if logical_id not in pools:
                names, pos, neg = load_pool(datasets[logical_id])
                pools[logical_id] = (names, pos, neg)
            names, pos, neg = pools[logical_id]
            # 生产口径：监控流量以正常样本为主，风险样本占少数 —— 取 35% 正类
            pool = pos if (pos and rng.random() < 0.35) else (neg or pos)
            row = rng.choice(pool)
            payload = {"model_version_id": model["id"],
                       "input_features": build_features(names, datasets[logical_id]["label_field"], row)}
            st, body = cli.post("/inference-records/predict", json=payload)
            if body.get("code") == 0:
                ok += 1
                if body["data"].get("is_risk_event"):
                    risk += 1
            else:
                fail += 1
                if len(errs) < 3:
                    errs.append(f"{st} {body.get('message')}")
        return username, ok, risk, fail, errs

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(run_account, u, r, c, s) for u, r, c, s in plan]
        for fut in futures:
            username, ok, risk, fail, errs = fut.result()
            results["ok"] += ok
            results["risk"] += risk
            results["fail"] += fail
            results["errors"].extend(errs)
            results["per_account"][username] = {"inference": ok, "risk_event": risk, "failed": fail}
            print(f"    {username:16s} 推理 {ok:4d}（风险 {risk:4d}）失败 {fail}")

    print(f"  合计：推理 {results['ok']} 条，生成风险事件 {results['risk']} 条，"
          f"失败 {results['fail']}，耗时 {round(time.perf_counter() - t0, 1)}s")
    state["inference"] = results
    return state


# ---------------------------------------------------------------------------
# 阶段五：处置记录
# ---------------------------------------------------------------------------
HANDLE_COMMENTS = [
    "已联系现场值班人员核实，告警属实，进入处置流程。",
    "初步判断为采集设备短时异常，已安排巡检复核。",
    "已按预案执行隔离与复核，指标恢复正常。",
    "与上游系统日志比对，确认非误报，已登记备案。",
    "现场反馈为周期性波动，暂列观察项，继续跟踪。",
    "已下发整改单，责任人跟进，两个工作日内反馈。",
    "复核后判定为环境因素导致，已调整采集参数。",
    "告警已闭环，处置过程与结论已归档。",
]


def stage_handling(state, max_events=400):
    admin = Client(SUPER_ADMIN)
    clients = {}
    handled = {"resolved": 0, "processing": 0, "comment": 0}

    # 各场景取一批待处置事件，交给事件创建者本人处置（场景用户只能处置本人事件）
    for sc in SCENARIOS:
        events = admin.data("GET", "/risk-events", params={
            "scenario_id": sc["id"], "status": "PENDING", "page": 1, "page_size": 200})["items"]
        rng = random.Random(f"handle-{sc['code']}")
        rng.shuffle(events)
        quota = min(len(events), max_events // len(SCENARIOS))
        for ev in events[:quota]:
            creator = ev["created_by_user_id"]
            cli = clients.get(creator)
            if cli is None:
                # 事件创建者是谁就用谁的账号处置（保持「本人处置本人告警」的口径）
                users = admin.data("GET", "/users", params={"page": 1, "page_size": 200})["items"]
                name = next((u["username"] for u in users if u["id"] == creator), None)
                if name is None:
                    continue
                cli = Client(name)
                clients[creator] = cli
            roll = rng.random()
            comment = rng.choice(HANDLE_COMMENTS)
            if roll < 0.45:
                st, body = cli.put(f"/risk-events/{ev['id']}/handle",
                                   json={"new_status": "RESOLVED", "comment": comment})
                if body.get("code") == 0:
                    handled["resolved"] += 1
            elif roll < 0.75:
                st, body = cli.put(f"/risk-events/{ev['id']}/handle",
                                   json={"new_status": "PROCESSING", "comment": comment})
                if body.get("code") == 0:
                    handled["processing"] += 1
                    if rng.random() < 0.6:
                        cli.put(f"/risk-events/{ev['id']}/handle",
                                json={"new_status": "RESOLVED", "comment": "处置完成，告警闭环。"})
                        handled["resolved"] += 1
            else:
                st, body = cli.post(f"/risk-events/{ev['id']}/comment", json={"comment": comment})
                if body.get("code") == 0:
                    handled["comment"] += 1

    print(f"  处置：已处置 {handled['resolved']}，处理中 {handled['processing']}，"
          f"仅追加说明 {handled['comment']}")
    state["handling"] = handled
    return state


# ---------------------------------------------------------------------------
# 阶段六：态势快照 + 态势报告
# ---------------------------------------------------------------------------
def stage_reports(state):
    admin = Client(SUPER_ADMIN)
    reports, snapshots = [], []

    # 快照：每个场景一条（管理级接口）
    for sc in SCENARIOS:
        try:
            res = admin.data("POST", f"/situation/scenes/{sc['id']}/snapshot")
            snapshots.append({"scenario_id": sc["id"], "id": res.get("id"), "total": res.get("total_events")})
            print(f"  [snapshot] {sc['code']:22s} 事件 {res.get('total_events')} "
                  f"高 {res.get('high_count')} 中 {res.get('medium_count')} 低 {res.get('low_count')}")
        except RuntimeError as exc:
            print(f"  ! 快照 {sc['code']} 失败: {exc}")

    # 超管：全平台聚合报告
    for title, scenario_id in [("全平台态势聚合报告", None),
                               ("网络安全态势聚合报告", 1),
                               ("电力系统态势聚合报告", 2)]:
        res = admin.data("POST", "/reports/generate",
                         json={"title": title, "scenario_id": scenario_id, "scope": "all", "format": "markdown"})
        reports.append({"id": res["id"], "title": title, "by": SUPER_ADMIN})
        print(f"  [report] {SUPER_ADMIN:12s} {title} -> #{res['id']}")

    # 场景管理员：本场景聚合报告 + 定时配置
    for sc in SCENARIOS:
        cli = Client(sc["admin"])
        title = f"{sc['code']} 场景态势聚合报告"
        res = cli.data("POST", "/reports/generate",
                       json={"title": title, "scenario_id": sc["id"], "scope": "all", "format": "markdown"})
        reports.append({"id": res["id"], "title": title, "by": sc["admin"]})
        cli.data("PUT", f"/reports/{res['id']}/schedule", json={"scheduled": True, "interval_days": 7})
        print(f"  [report] {sc['admin']:12s} {title} -> #{res['id']}（已设 7 天定时）")

    state["reports"] = reports
    state["snapshots"] = snapshots
    return state


# ---------------------------------------------------------------------------
# 阶段七：时间轴铺开
# ---------------------------------------------------------------------------
def _spread(rng, days, recent_share=0.45, recent_window=7):
    """返回「距今多少天」（带小数）：近期窗口内密集，其余摊到 days 天里。

    直接返回小数天、不再额外加随机秒数 —— 加了会把整体时间轴整体往前推半天，
    导致「今天」这根柱子在近 7 天趋势图里塌掉。
    """
    if rng.random() < recent_share:
        return rng.uniform(0, recent_window)
    return rng.uniform(recent_window, days)


def stage_timeline(state, days=60):
    """把「都是刚刚」的时间戳改成近 N 天的分布。

    真实接口生成的数据时间戳都是 now，趋势图会退化成今天一根柱子。
    这里按事件时间统一回填：风险事件 occurred_at 与其推理记录 executed_at 同值，
    处置记录晚于事件，模型训练/发布时间落在更早的区间。
    """
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models.handling_record import HandlingRecord
    from app.models.inference_record import InferenceRecord
    from app.models.model_version import ModelVersion
    from app.models.report import Report
    from app.models.risk_event import RiskEvent
    from app.models.situation_snapshot import SituationSnapshot

    rng = random.Random(20260920)
    now = datetime.now(timezone.utc)
    stats = {}

    with SessionLocal() as db:
        events = db.scalars(select(RiskEvent)).all()
        for ev in events:
            when = now - timedelta(days=_spread(rng, days))
            ev.occurred_at = when
            record = db.get(InferenceRecord, ev.inference_record_id)
            if record is not None:
                record.executed_at = when
        stats["risk_events"] = len(events)

        # 未生成事件的推理记录：独立铺开
        event_record_ids = {ev.inference_record_id for ev in events}
        others = db.scalars(select(InferenceRecord)).all()
        n_other = 0
        for record in others:
            if record.id in event_record_ids:
                continue
            record.executed_at = now - timedelta(days=_spread(rng, days))
            n_other += 1
        stats["inference_records"] = len(others)

        # 处置记录：紧跟事件之后
        for hr in db.scalars(select(HandlingRecord)).all():
            ev = db.get(RiskEvent, hr.risk_event_id)
            base = ev.occurred_at if ev is not None and ev.occurred_at else now - timedelta(days=days)
            hr.created_at = base + timedelta(minutes=rng.randint(20, 2880))

        # 模型：训练时间落在 30~120 天前，发布时间晚几小时
        for mv in db.scalars(select(ModelVersion)).all():
            trained = now - timedelta(days=rng.uniform(30, 120), seconds=rng.randint(0, 86399))
            mv.trained_at = trained
            if mv.published_at is not None:
                mv.published_at = trained + timedelta(hours=rng.randint(1, 72))
        stats["models"] = len(db.scalars(select(ModelVersion)).all())

        # 报告 / 快照
        for rp in db.scalars(select(Report)).all():
            rp.generated_at = now - timedelta(days=rng.uniform(0, 20), seconds=rng.randint(0, 86399))
        for sn in db.scalars(select(SituationSnapshot)).all():
            sn.snapshot_time = now - timedelta(days=rng.uniform(0, 5), seconds=rng.randint(0, 86399))

        db.commit()

    print(f"  时间轴：{stats['risk_events']} 条风险事件 / {stats['inference_records']} 条推理记录 "
          f"/ {stats['models']} 个模型版本铺到近 {days} 天")
    state["timeline"] = stats
    return state


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
STAGES = {
    "accounts": stage_accounts,
    "datasets": stage_datasets,
    "models": stage_models,
    "handling": stage_handling,
    "reports": stage_reports,
}

# --all 必须按依赖顺序显式列出：处置依赖推理产出的事件，
# 直接用 dict 顺序会把 handling 排到 inference 前面 —— 空库上等于静默跳过。
ALL_STAGES = ["accounts", "datasets", "models", "inference", "handling", "reports", "timeline"]


def main():
    parser = argparse.ArgumentParser(description="虚拟生产数据注入")
    parser.add_argument("--stage", default="accounts,datasets,models",
                        help="逗号分隔：accounts,datasets,models,inference,handling,reports,timeline")
    parser.add_argument("--all", action="store_true", help="跑全部阶段")
    parser.add_argument("--inferences", type=int, default=2000, help="推理总条数（近似）")
    parser.add_argument("--accounts", default=None, help="仅对指定账号跑推理（逗号分隔）")
    parser.add_argument("--days", type=int, default=60, help="时间轴铺开的天数")
    args = parser.parse_args()

    stages = ALL_STAGES if args.all else \
        [s.strip() for s in args.stage.split(",") if s.strip()]

    state = {"started_at": datetime.now().isoformat(timespec="seconds")}
    print("=" * 72)
    print(f"虚拟生产数据注入：{' → '.join(stages)}")
    print("=" * 72)

    for stage in stages:
        print(f"\n[{stage}]")
        if stage == "inference":
            only = [a.strip() for a in args.accounts.split(",")] if args.accounts else None
            state = stage_inference(state, args.inferences, only)
        elif stage == "timeline":
            state = stage_timeline(state, args.days)
        elif stage in STAGES:
            state = STAGES[stage](state)
        else:
            print(f"  ! 未知阶段 {stage}")

    state["finished_at"] = datetime.now().isoformat(timespec="seconds")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n注入清单已写入 {REPORT_PATH}")


if __name__ == "__main__":
    main()
