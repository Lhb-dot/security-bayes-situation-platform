import time
import os

# 数据集根路径
DATA_ROOT = "./data"

# 1. 获取全部数据集列表接口逻辑
def get_dataset_list():
    dataset_dirs = os.listdir(DATA_ROOT)
    res = []
    for d in dataset_dirs:
        path = os.path.join(DATA_ROOT, d)
        if os.path.isdir(path):
            desc_map = {
                "nf_unsw": "网络安全NF-UNSW入侵流量数据集",
                "power_data": "电力系统设备故障数据集",
                "carrier_sim": "航母舰面作业碰撞仿真数据集"
            }
            res.append({
                "dataset_name": d,
                "path": path,
                "description": desc_map.get(d, "自定义数据集")
            })
    return res

# 2. 模拟贝叶斯模型训练
def train_bayes_sim(dataset_name: str, algo_type: str, discrete_method: str):
    time.sleep(2)
    mock_metrics = {
        "recall_minority": 0.93,
        "g_mean": 0.91,
        "f1": 0.92,
        "accuracy": 0.95
    }
    return {
        "status": "训练完成",
        "dataset": dataset_name,
        "algorithm": algo_type,
        "discrete_method": discrete_method,
        "train_cost_time": "2.0s",
        "evaluation_metrics": mock_metrics
    }

# 3. 模拟贝叶斯单条数据风险推理
def infer_bayes_sim(input_data: dict):
    feature_weight_list = [
        {"feature": "流量长度", "weight": 0.38},
        {"feature": "连接时长", "weight": 0.32},
        {"feature": "访问频次", "weight": 0.18},
        {"feature": "目标端口", "weight": 0.12}
    ]
    reason_text = """
1. 使用MDLP有监督离散化处理原始监测特征，构建基础概率视图；
2. 基于随机树与SPODE生成潜在软概率视图，形成加权矩阵；
3. 通过矩阵加权贝叶斯计算后验风险概率，判定本条数据为高危风险；
4. 高权重特征是流量长度、连接时长，为本条风险主要诱因。
    """.strip()
    return {
        "risk_level": "高危",
        "risk_type": "DoS拒绝服务攻击",
        "risk_probability": 0.96,
        "feature_weight": feature_weight_list,
        "infer_explain": reason_text
    }