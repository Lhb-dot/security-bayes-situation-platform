"""
services/model_sim.py — PMWNB 贝叶斯模型服务（对接 Java PMWNB HTTP 服务）

Java PMWNB 服务默认运行在 http://127.0.0.1:12313
数据集路径映射到 data/ 目录下的 CSV 文件
"""
import os
import requests
from app.algorithms.pmwnb_demo import global_threshold

# Java PMWNB 服务地址
PMWNB_SERVICE_URL = os.getenv("PMWNB_SERVICE_URL", "http://127.0.0.1:12313")

# 项目根目录与后端根目录
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # backend/
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)                                 # security-bayes-platform/

# 数据集路径映射（指向根目录 data/，与 pmwnb_demo.py 一致）
DATASET_PATH_MAP = {
    "net_attack_2024": os.path.join(PROJECT_ROOT, "data", "nf_unsw", "sample_demo.csv"),
    "power_outage":    os.path.join(PROJECT_ROOT, "data", "power_data", "sample_demo.csv"),
    "carrier_deck":    os.path.join(PROJECT_ROOT, "data", "carrier_sim", "sample_demo.csv"),
}

# 模型保存目录
TRAINED_MODEL_DIR = os.path.join(BACKEND_ROOT, "storage", "models")
os.makedirs(TRAINED_MODEL_DIR, exist_ok=True)

# ===================== 接口函数（供 server.py 调用） =====================

def get_dataset_list():
    """1. 获取全部数据集列表"""
    return [
        {"dataset_name": "net_attack_2024", "description": "网络入侵流量数据集"},
        {"dataset_name": "power_outage",    "description": "电力停电风险数据集"},
        {"dataset_name": "carrier_deck",    "description": "航母舰面调度数据集"},
    ]


def train_bayes_sim(dataset_name: str, algo_type: str, discrete_method: str) -> dict:
    """
    2. 调用 Java PMWNB 服务进行模型训练
    返回格式: {"accuracy": ..., "f1": ..., "recall": ..., "train_time_s": ...}
    """
    csv_path = DATASET_PATH_MAP.get(dataset_name)
    if not csv_path or not os.path.exists(csv_path):
        raise FileNotFoundError(f"数据集文件不存在: {csv_path}")

    model_save_path = os.path.join(TRAINED_MODEL_DIR, f"pmwnb_{dataset_name}.model")

    try:
        resp = requests.post(
            f"{PMWNB_SERVICE_URL}/train",
            json={
                "dataset_path": csv_path,
                "model_save_path": model_save_path,
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"无法连接到 PMWNB 服务 ({PMWNB_SERVICE_URL})，请先启动 Java 服务：\n"
            f"  java -jar target/pmwnb-service-1.0.0.jar 12313"
        )

    if not result.get("success"):
        raise RuntimeError(f"PMWNB 训练失败: {result.get('error', '未知错误')}")

    metrics = result["metrics"]
    return {
        "accuracy":         metrics["accuracy"],
        "f1":               metrics["f1"],
        "recall":           metrics["recall"],
        "train_time_s":     metrics["train_time_s"],
        "status":           "训练完成",
        "dataset":          metrics.get("dataset", dataset_name),
        "algorithm":        algo_type,
        "discrete_method":  discrete_method,
        "num_instances":    metrics.get("num_instances", 0),
        "evaluation_metrics": {
            "recall_minority": metrics["recall"],
            "g_mean":          round((metrics["accuracy"] * metrics["recall"]) ** 0.5, 4),
            "f1":              metrics["f1"],
            "accuracy":        metrics["accuracy"],
        },
    }


def infer_bayes_sim(input_data: dict) -> dict:
    """
    3. 调用 Java PMWNB 服务进行单条流量风险推理
    返回格式: {"risk_level": ..., "risk_probability": ..., ...}
    """
    flow_length = float(input_data.get("flowLength", 0))
    duration    = float(input_data.get("duration", 0))
    access_freq = float(input_data.get("accessFreq", 0))

    try:
        resp = requests.post(
            f"{PMWNB_SERVICE_URL}/predict",
            json={
                "flowLength": flow_length,
                "duration":   duration,
                "accessFreq": access_freq,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"无法连接到 PMWNB 服务 ({PMWNB_SERVICE_URL})，请先启动 Java 服务"
        )

    if not result.get("success"):
        raise RuntimeError(f"PMWNB 推理失败: {result.get('error', '未知错误')}")

    data = result["data"]
    raw_prob = data["risk_probability"]
    all_probs = data.get("all_probabilities", [])

    # 用全部类别概率做加权归一化，与 pmwnb_demo.risk_infer_sim 保持一致
    if all_probs and isinstance(all_probs, list) and len(all_probs) >= 2:
        try:
            # 格式: [{"class": "高风险", "probability": 0.3874}, ...]
            if isinstance(all_probs[0], dict):
                def _label_score(label):
                    s = str(label)
                    if "高" in s: return 3
                    if "中" in s: return 2
                    if "低" in s: return 1
                    return 2
                scores = [_label_score(p.get("class", p.get("label", ""))) for p in all_probs]
                probs = [p.get("probability", p.get("prob", 0)) for p in all_probs]
                score_min, score_max = min(scores), max(scores)
                weighted = sum(p * s for p, s in zip(probs, scores))
                if score_max == score_min:
                    risk_prob = 0.5
                else:
                    risk_prob = round((weighted - score_min) / (score_max - score_min), 4)
            else:
                risk_prob = raw_prob
        except Exception:
            risk_prob = raw_prob
    else:
        risk_prob = raw_prob

    # 按全局阈值从高→中→低顺序判定（覆盖Java原始level，确保与前端阈值配置一致）
    high = global_threshold.get("high", 0.75)
    mid  = global_threshold.get("mid",  0.45)
    low  = global_threshold.get("low",  0.2)

    if risk_prob >= high:
        risk_level = "高危"
    elif risk_prob >= mid:
        risk_level = "中风险"
    elif risk_prob >= low:
        risk_level = "低风险"
    else:
        risk_level = "无风险"

    return {
        "risk_level":       risk_level,
        "risk_type":        data.get("risk_type", "矩阵加权贝叶斯PMWNB推理"),
        "risk_probability": risk_prob,
        "feature_weight":   data.get("feature_weight", []),
        "infer_explain":    data.get("infer_explain", "PMWNB 双视图矩阵加权贝叶斯推理"),
        "all_probabilities": data.get("all_probabilities", []),
    }


# ===================== 健康检查 =====================

def check_service_health() -> bool:
    """检查 Java PMWNB 服务是否正常运行"""
    try:
        resp = requests.get(f"{PMWNB_SERVICE_URL}/health", timeout=3)
        return resp.status_code == 200 and resp.json().get("status") == "ok"
    except Exception:
        return False
