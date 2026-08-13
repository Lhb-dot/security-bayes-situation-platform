"""training_executor.py — 模型训练执行器（需求 6.7.1 训练并保存真实指标）

策略：
- PMWNB：调用 Java PMWNB 服务（backend/lib/pmwnb-service.jar，weka 真实算法）
  对已注册的 ARFF 数据集训练，指标来自服务返回的真实评估结果；
- 其余算法（A2WNB/MAWNB/EMAWNB/DIWNB）：算法实现待算法组交付，暂以 mock 占位指标
  落库（evaluation_metrics.source = "mock" 标记，前端据此提示"模拟数据"）。

Java 服务 /train 契约（见 lib/pmwnb-service.jar TrainHandler）：
    POST {PMWNB_SERVICE_URL}/train
    body: {dataset_path: str(必填), model_save_path: str(可选)}
    resp: {success: bool, metrics: {accuracy, f1, recall, precision,
           train_time_s, num_instances, num_attributes, num_classes,
           class_distribution, model_saved_to}}
"""
import os
import random

import requests

from app.services.model_sim import PMWNB_SERVICE_URL, TRAINED_MODEL_DIR

# Java 服务训练超时（秒）：大数据集（KDD 20% 约 45k 行）需留足余量
PMWNB_TRAIN_TIMEOUT = 240


def resolve_dataset_path(file_path: str) -> str:
    """把 dataset.file_path（相对项目根，如 data/power/xxx.arff）解析为绝对路径。"""
    if os.path.isabs(file_path):
        return file_path
    from app.services.model_sim import PROJECT_ROOT
    return os.path.join(PROJECT_ROOT, file_path)


def execute_pmwnb_training(dataset_path: str, model_save_path: str) -> dict:
    """调用 Java PMWNB /train，返回真实评估指标（source=java_pmwnb）。

    抛错：FileNotFoundError / RuntimeError（服务不可达或训练失败）。
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"数据集文件不存在: {dataset_path}")

    try:
        resp = requests.post(
            f"{PMWNB_SERVICE_URL}/train",
            json={"dataset_path": dataset_path, "model_save_path": model_save_path},
            timeout=PMWNB_TRAIN_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"无法连接到 PMWNB 算法服务（{PMWNB_SERVICE_URL}），"
            f"请先启动 Java 服务：java -jar lib/pmwnb-service.jar 12313"
        )

    if not result.get("success"):
        raise RuntimeError(result.get("error", "PMWNB 训练失败"))

    metrics = result["metrics"]
    return {
        "source": "java_pmwnb",               # 前端据此标记"真实训练"
        "accuracy": metrics["accuracy"],
        "f1": metrics["f1"],
        "recall": metrics["recall"],
        "precision": metrics["precision"],
        "train_time_s": metrics["train_time_s"],
        "num_instances": metrics.get("num_instances", 0),
        "num_attributes": metrics.get("num_attributes", 0),
        "num_classes": metrics.get("num_classes", 0),
        "class_distribution": metrics.get("class_distribution", []),
        "model_saved_to": metrics.get("model_saved_to", ""),
        "dataset": metrics.get("dataset", dataset_path),
    }


def mock_training_metrics(algorithm_code: str) -> dict:
    """其余算法占位训练指标（source=mock，算法实现待交付）。"""
    rng = random.Random(algorithm_code)  # 同一算法多次训练结果稳定
    N = 1000
    tp = rng.randint(380, 540)
    fn = rng.randint(30, 90)
    fp = rng.randint(25, 80)
    tn = N - tp - fn - fp
    accuracy = (tp + tn) / N
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    specificity = tn / (tn + fp)
    f1 = 2 * precision * recall / (precision + recall)
    g_mean = (recall * specificity) ** 0.5
    round4 = lambda v: round(v, 4)
    return {
        "source": "mock",                     # 前端据此标记"模拟占位"
        "accuracy": round4(accuracy),
        "recall": round4(recall),
        "precision": round4(precision),
        "specificity": round4(specificity),
        "f1": round4(f1),
        "g_mean": round4(g_mean),
        "train_time_s": round(rng.uniform(0.5, 3.0), 1),
        "algorithm_code": algorithm_code,
    }


def build_model_save_path(model_id: int) -> str:
    """模型文件保存路径（backend/storage/models/pmwnb_mv{id}.model）。"""
    os.makedirs(TRAINED_MODEL_DIR, exist_ok=True)
    return os.path.join(TRAINED_MODEL_DIR, f"pmwnb_mv{model_id}.model")
