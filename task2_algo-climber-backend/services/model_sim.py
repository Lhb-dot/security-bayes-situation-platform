"""
services/model_sim.py — PMWNB 贝叶斯模型服务（对接 Java PMWNB HTTP 服务）

Java PMWNB 服务默认运行在 http://127.0.0.1:12313
数据集路径映射到 data/ 目录下的 CSV 文件
"""
import os
import requests

# Java PMWNB 服务地址
PMWNB_SERVICE_URL = os.getenv("PMWNB_SERVICE_URL", "http://127.0.0.1:12313")

# 数据集根路径（相对于后端项目根目录）
BASE_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_ROOT = os.path.join(BASE_ROOT, "data")

# 数据集路径映射（与 pmwnb_demo.py 中的 DATASET_PATH_MAP 一致）
DATASET_PATH_MAP = {
    "net_attack_2024": os.path.join(DATA_ROOT, "nf_unsw", "sample_demo.csv"),
    "power_outage":    os.path.join(DATA_ROOT, "power_data", "sample_demo.csv"),
    "carrier_deck":    os.path.join(DATA_ROOT, "carrier_sim", "sample_demo.csv"),
}

# 模型保存目录
TRAINED_MODEL_DIR = os.path.join(BASE_ROOT, "trained_models")
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
    return {
        "risk_level":       data["risk_level"],
        "risk_type":        data.get("risk_type", "矩阵加权贝叶斯PMWNB推理"),
        "risk_probability": data["risk_probability"],
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
