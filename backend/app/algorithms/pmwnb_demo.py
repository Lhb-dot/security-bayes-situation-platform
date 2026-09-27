# app/algorithms/pmwnb_demo.py — 遗留「兼容接口」的进程内状态与阈值。
#
# 训练/推理实现（sklearn GaussianNB）已被 Java PMWNB 服务取代，且逐字重复在
# app/services/model_sim.py 中——本模块的 train_model_sim / risk_infer_sim /
# get_dataset_list_sim 三个函数**零引用**（旧路由 /api/model/train、/api/model/infer
# 走的是 model_sim.train_bayes_sim / infer_bayes_sim），已删除，
# 证据见 docs/全项目代码审查/报告/B6b-1.md。
#
# 保留部分仅服务 app/api/legacy_model_routes.py（/api/model/save-threshold、
# /api/model/exp-records、/api/model/exp/{id}）与 model_sim.infer_bayes_sim 读取的
# global_threshold。整条兼容链路是否下线由 Lead 裁决（见 待裁决.md）。
import threading

# 保留原有前端联动全局变量：阈值、实验记录列表
global_threshold = {"high": 0.75, "mid": 0.45, "low": 0.2}
exp_records = []
record_id = 1

# 线程锁：保护 exp_records / record_id 的并发读写安全
_exp_lock = threading.Lock()


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


# 2. 自定义阈值保存函数，原样保留
def save_threshold_sim(h, m, l):
    global global_threshold
    if h > m > l:
        global_threshold["high"] = h
        global_threshold["mid"] = m
        global_threshold["low"] = l
        return True
    return False


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
