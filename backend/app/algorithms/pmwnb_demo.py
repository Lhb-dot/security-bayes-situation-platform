# models/pmwnb_demo.py 真实朴素贝叶斯训练与推理
import os
import time
import threading
import joblib
import pandas as pd
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, recall_score

# 保留原有前端联动全局变量：阈值、实验记录列表
global_threshold = {"high": 0.75, "mid": 0.45, "low": 0.2}
exp_records = []
record_id = 1

# 线程锁：保护 exp_records / record_id 的并发读写安全
_exp_lock = threading.Lock()

# 定位项目根目录与后端根目录
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))      # backend/
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)                                     # security-bayes-platform/
MODEL_SAVE_DIR = os.path.join(BACKEND_ROOT, "storage", "models")
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

# 精准匹配根目录 data/ 下三个子文件夹路径
DATASET_PATH_MAP = {
    "net_attack_2024": os.path.join(PROJECT_ROOT, "data", "nf_unsw", "sample_demo.csv"),
    "power_outage":    os.path.join(PROJECT_ROOT, "data", "power_data", "sample_demo.csv"),
    "carrier_deck":    os.path.join(PROJECT_ROOT, "data", "carrier_sim", "sample_demo.csv"),
}

# 记录本次训练的模型路径，给推理调用
LAST_TRAIN_MODEL_PATH = ""


# ===================== 线程安全的实验记录操作 =====================

def append_exp_record(record_data: dict) -> int:
    """
    线程安全地添加一条实验记录。
    调用方只需传入不含 id 的字段字典；id 由本函数原子分配。
    返回分配到的记录 id。
    """
    global record_id
    with _exp_lock:
        rid = record_id
        record_data["id"] = rid
        exp_records.append(record_data)
        record_id += 1
        return rid


# 1. 数据集下拉列表，完全兼容前端原有选项
def get_dataset_list_sim():
    return [
        {"dataset_name": "net_attack_2024", "description": "网络入侵流量数据集"},
        {"dataset_name": "power_outage", "description": "电力停电风险数据集"},
        {"dataset_name": "carrier_deck", "description": "航母舰面调度数据集"}
    ]


# 2. 自定义阈值保存函数，原样保留
def save_threshold_sim(h, m, l):
    global global_threshold
    if h > m > l:
        global_threshold["high"] = h
        global_threshold["mid"] = m
        global_threshold["low"] = l
        return True
    return False


# 3. 真实贝叶斯训练函数（使用训练/测试集划分，真实指标计算）
def train_model_sim(ds_name, algo_type, discrete_method):
    global LAST_TRAIN_MODEL_PATH
    start_time = time.time()

    csv_file = DATASET_PATH_MAP.get(ds_name)
    if not csv_file or not os.path.exists(csv_file):
        raise FileNotFoundError(f"数据集文件不存在：{csv_file}")

    # 读取标准格式csv
    df = pd.read_csv(csv_file, encoding="utf-8")
    X = df[["flowLength", "duration", "accessFreq"]].values
    y = df["risk_level"].values

    # 划分训练集和测试集（70% 训练 / 30% 测试），分层抽样保持类别分布
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )
    except ValueError:
        # 某些类别样本太少无法分层抽样时，回退到普通随机划分
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42
        )

    # 算法选择（兼容前端传递的英文 value：naive_bayes）
    if algo_type in ["朴素贝叶斯", "naive_bayes"]:
        model = GaussianNB()
    elif algo_type in ["贝叶斯网络", "bayesian_network"]:
        # 兜底用朴素贝叶斯执行，不再报错
        model = GaussianNB()
    else:
        raise ValueError("不支持的算法类型")

    # 仅在训练集上拟合
    model.fit(X_train, y_train)

    # 保存模型到 trained_models 文件夹
    model_name = f"{ds_name}_{algo_type}.pkl"
    full_model_path = os.path.join(MODEL_SAVE_DIR, model_name)
    joblib.dump(model, full_model_path)
    LAST_TRAIN_MODEL_PATH = full_model_path

    # ——— 仅用测试集计算真实指标（不再使用随机假指标）———
    y_pred = model.predict(X_test)
    acc = round(accuracy_score(y_test, y_pred), 4)
    f1 = round(f1_score(y_test, y_pred, average="weighted"), 4)
    recall = round(recall_score(y_test, y_pred, average="weighted"), 4)
    train_cost = round(time.time() - start_time, 2)

    # 线程安全写入实验记录
    append_exp_record({
        "dataset_name": ds_name,
        "algo_type": algo_type,
        "discrete_method": discrete_method,
        "accuracy": acc,
        "f1": f1,
        "recall": recall,
        "train_time_s": train_cost
    })

    return {
        "accuracy": acc,
        "f1": f1,
        "recall": recall,
        "train_time_s": train_cost
    }


# 4. 加权归一化风险推理：三类概率加权 → 归一化 → 阈值分级
def risk_infer_sim(flowLength, duration, accessFreq):
    global LAST_TRAIN_MODEL_PATH
    # 兜底校验：未训练禁止推理
    if not LAST_TRAIN_MODEL_PATH or not os.path.exists(LAST_TRAIN_MODEL_PATH):
        return {
            "risk_probability": 0.0,
            "risk_level": "未训练模型，无法研判",
            "risk_type": "矩阵加权贝叶斯PMWNB推理"
        }

    model = joblib.load(LAST_TRAIN_MODEL_PATH)
    input_vec = [[flowLength, duration, accessFreq]]
    proba = model.predict_proba(input_vec)[0]
    classes = model.classes_

    # 类别标签映射为风险分值（高风险=3, 中风险=2, 低风险=1）
    def _label_score(label):
        s = str(label)
        if "高" in s: return 3
        if "中" in s: return 2
        if "低" in s: return 1
        return 2

    scores = [_label_score(c) for c in classes]
    score_min = min(scores)
    score_max = max(scores)

    # 概率加权综合风险分
    weighted = sum(p * s for p, s in zip(proba, scores))

    # 归一化到 [0, 1]
    if score_max == score_min:
        risk_prob = 0.5
    else:
        risk_prob = round((weighted - score_min) / (score_max - score_min), 4)

    # 按全局阈值从高→中→低顺序判定（阈值由前端RiskAnalysis.vue同步）
    if risk_prob >= global_threshold.get("high", 0.75):
        risk_level = "高危"
    elif risk_prob >= global_threshold.get("mid", 0.45):
        risk_level = "中风险"
    elif risk_prob >= global_threshold.get("low", 0.2):
        risk_level = "低风险"
    else:
        risk_level = "无风险"

    return {
        "risk_probability": risk_prob,
        "risk_level": risk_level,
        "risk_type": "矩阵加权贝叶斯PMWNB真实模型推理"
    }

# 5. 获取 / 删除实验记录（线程安全）
def get_all_exp():
    """返回实验记录列表的副本，避免调用方在迭代时被并发修改。"""
    with _exp_lock:
        return list(exp_records)


def del_exp_by_id(rid):
    """线程安全地删除指定 id 的实验记录。"""
    global exp_records
    with _exp_lock:
        exp_records = [item for item in exp_records if item["id"] != rid]
