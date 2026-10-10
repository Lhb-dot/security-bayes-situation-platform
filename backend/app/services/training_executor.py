"""Java 算法训练/预测执行器。

PMWNB 使用既有服务；A2WNB、MAWNB、EMAWNB、CAVWNB 使用由
scripts/build_nb_algorithm_jars.ps1 编译的真实 Weka 算法服务。所有训练
指标均来自 Java 分类器，不再生成 mock 指标。
"""
import os

import requests

from app.paths import PROJECT_ROOT
from app.services.algorithm_config import (
    ALGORITHM_SERVICE_URLS,
    PMWNB_SERVICE_URL,
    PREDICT_SERVICE_URL,
    PREDICT_TIMEOUT,
    TRAIN_TIMEOUT,
    TRAINED_MODEL_DIR,
)


def resolve_dataset_path(file_path: str) -> str:
    """把 dataset.file_path 解析成可读的绝对路径（全项目读数据集文件的唯一入口）。

    历史数据里存在 Windows 反斜杠写法（``data\\network\\X.arff``）。在 Windows 上
    它能被当作路径分隔符正常解析，但在 Linux 上 ``os.path.isabs`` 判否、拼接后
    整串会被当成**一个文件名**，于是 ``os.path.exists`` 恒为 False —— 表现为首页
    「各场景有效样本量 / 风险占比」全是 0，且没有任何报错。

    统一先归一化成 ``/`` 再判断与拼接，两个平台都能解析；正斜杠在 Windows 上同样
    是合法分隔符，因此对已有的正斜杠数据无影响。
    """
    normalized = str(file_path).replace("\\", "/")
    if os.path.isabs(normalized):
        return normalized
    return str(PROJECT_ROOT / normalized)


def _request_train(
    url: str,
    algorithm_code: str,
    dataset_path: str,
    model_save_path: str,
    training_parameters: dict | None = None,
    risk_labels: list[str] | None = None,
) -> dict:
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"数据集文件不存在: {dataset_path}")
    try:
        resp = requests.post(
            f"{url}/train",
            json={
                "algorithm_code": algorithm_code,
                "dataset_path": dataset_path,
                "model_save_path": model_save_path,
                "training_parameters": training_parameters or {},
                "risk_labels": risk_labels or [],
            },
            timeout=TRAIN_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"无法连接到 {algorithm_code} 算法服务（{url}），"
            "请先运行 start_all.ps1 启动 Java 算法服务"
        ) from exc
    except requests.exceptions.RequestException as exc:
        # 超时 / HTTP 错误状态码原先以原始异常逃逸，最终只剩无信息的 500
        raise RuntimeError(f"{algorithm_code} 算法服务请求失败（{url}）：{exc}") from exc
    if not result.get("success"):
        raise RuntimeError(result.get("error", f"{algorithm_code} 训练失败"))
    metrics = result["metrics"]
    return {
        "source": f"java_{algorithm_code.lower()}",
        "algorithm_code": algorithm_code,
        "accuracy": metrics["accuracy"],
        "f1": metrics["f1"],
        "recall": metrics["recall"],
        "precision": metrics["precision"],
        "specificity": metrics.get("specificity"),
        "g_mean": metrics.get("g_mean"),
        "risk_recall": metrics.get("risk_recall"),
        "risk_f1": metrics.get("risk_f1"),
        "cv_mean": metrics.get("cv_mean"),
        "cv_std": metrics.get("cv_std"),
        "quality_availability": metrics.get("quality_availability", {}),
        "train_time_s": metrics.get("train_time_s", 0.0),
        "num_instances": metrics.get("num_instances", 0),
        "num_attributes": metrics.get("num_attributes", 0),
        "num_classes": metrics.get("num_classes", 0),
        "class_distribution": metrics.get("class_distribution", []),
        "model_saved_to": metrics.get("model_saved_to", model_save_path),
        "dataset": metrics.get("dataset", dataset_path),
    }


def execute_algorithm_training(
    algorithm_code: str,
    dataset_path: str,
    model_save_path: str,
    training_parameters: dict | None = None,
    risk_labels: list[str] | None = None,
) -> dict:
    code = algorithm_code.upper()
    if code == "PMWNB":
        return execute_pmwnb_training(dataset_path, model_save_path, training_parameters, risk_labels)
    url = ALGORITHM_SERVICE_URLS.get(code)
    if not url:
        raise RuntimeError(f"未配置 {code} 算法服务")
    return _request_train(url, code, dataset_path, model_save_path, training_parameters, risk_labels)


def execute_pmwnb_training(
    dataset_path: str,
    model_save_path: str,
    training_parameters: dict | None = None,
    risk_labels: list[str] | None = None,
) -> dict:
    # _request_train 已按 algorithm_code 生成 source="java_pmwnb"，此处无需再覆盖。
    return _request_train(
        PMWNB_SERVICE_URL, "PMWNB", dataset_path, model_save_path, training_parameters, risk_labels
    )


def build_model_save_path(model_id: int, algorithm_code: str = "PMWNB") -> str:
    os.makedirs(TRAINED_MODEL_DIR, exist_ok=True)
    return os.path.join(TRAINED_MODEL_DIR, f"{algorithm_code.lower()}_mv{model_id}.model")


def _request_predict(
    url: str,
    algorithm_code: str,
    model_path: str,
    arff_path: str,
    features: dict,
    risk_labels: list[str] | None = None,
) -> dict:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    if not os.path.exists(arff_path):
        raise FileNotFoundError(f"数据集文件不存在: {arff_path}")
    try:
        resp = requests.post(
            f"{url}/predict",
            json={
                "algorithm_code": algorithm_code,
                "model_path": model_path,
                "arff_path": arff_path,
                "features": features,
                "risk_labels": risk_labels or [],
            },
            timeout=PREDICT_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"无法连接到 Java 预测服务（{url}）") from exc
    except requests.exceptions.RequestException as exc:
        # 同上：超时 / HTTP 错误原先逃逸成无信息的 500
        raise RuntimeError(f"Java 预测服务请求失败（{url}）：{exc}") from exc
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Java 预测失败"))
    return result["data"]


def execute_algorithm_predict(
    algorithm_code: str,
    model_path: str,
    arff_path: str,
    features: dict,
    risk_labels: list[str] | None = None,
) -> dict:
    code = algorithm_code.upper()
    url = PREDICT_SERVICE_URL if code == "PMWNB" else ALGORITHM_SERVICE_URLS.get(code)
    if not url:
        raise RuntimeError(f"未配置 {code} 算法服务")
    return _request_predict(url, code, model_path, arff_path, features, risk_labels)
