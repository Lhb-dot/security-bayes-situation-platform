"""scenario_analytics.py — 场景差异化辅助计算（V3.0 §8：贝叶斯分类前后的辅助判断层）。

第 8 节要求：不同场景在其数据集字段基础上提供特有的数据加工/轻量计算，供前端
大屏（第 7 节卡片/图表/列表）使用。本模块实现后端侧的计算服务，输入统一为
ARFF 解析结果（fields + rows），输出按场景结构化的洞察 JSON。

口径与边界：
- 全部为只读聚合计算，不落库、不依赖模型；训练/推理链路不变。
- 计算行数有界（默认取前 500 行），大文件只算样本，接口保证快速返回。
- 字段缺失时跳过对应项，不虚构数据。
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any, Dict, List, Optional

from app.services.constants import (
    RISK_TYPE_FLIGHT_DECK,
    RISK_TYPE_GEOLOGICAL,
    RISK_TYPE_NETWORK,
    RISK_TYPE_POWER,
    is_risk_label,
)


def _col_map(fields: List[Dict]) -> Dict[str, int]:
    """字段名 → 列号映射。"""
    return {f["name"]: i for i, f in enumerate(fields)}


def _pick_idx(cmap: Dict[str, int], *names: str) -> Optional[int]:
    """按候选名依次取第一个存在的列号；候选名都不存在时返回 None。

    各场景洞察原先各自定义了一份同名的闭包 ``idx``，此处收敛为单一实现。
    """
    for name in names:
        if name in cmap:
            return cmap[name]
    return None


def _label_is_risk(logical_id: Optional[str], value: str) -> bool:
    """标签是否正类（风险）——只认显式登记表。

    口径唯一真源是 ``constants.DATASET_POSITIVE_LABELS``。需求 6.4.1 明令禁止按标签字符串 /
    取值大小 / 文件排列顺序自动推断正类，因此未登记的数据集（logical_id 缺失或未登记）
    一律返回 False：宁可少报异常样本，也不猜（异常样本数会由 API 的 logical_id 字段自证口径）。
    """
    if not logical_id:
        return False
    return is_risk_label(logical_id, value)


_INTERVAL_RE = re.compile(r"[\[(]\s*([-0-9.]+)\s*[-~,]\s*([-0-9.]+)\s*[\])]")


def _to_float(v: str) -> Optional[float]:
    """把值转 float；支持地质离散化区间 `(a-b]` → 取中点（§3.6 数据已离散化）。"""
    if v in (None, "", "?"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        pass
    m = _INTERVAL_RE.search(v)
    if m:
        try:
            a, b = float(m.group(1)), float(m.group(2))
            return round((a + b) / 2, 4)
        except (TypeError, ValueError):
            return None
    return None


def _col(rows: List[List[str]], idx: int) -> List[float]:
    """取某列并转 float（含区间值中点解析），非数值行丢弃。"""
    out: List[float] = []
    for r in rows:
        if idx < len(r):
            val = _to_float(r[idx])
            if val is not None:
                out.append(val)
    return out


def _top_counts(values: List[str], top_n: int = 10) -> List[Dict[str, Any]]:
    cnt = Counter(v for v in values if v not in ("", "?"))
    return [{"value": k, "count": c} for k, c in cnt.most_common(top_n)]


# ---------------------------------------------------------------------------
# 网络安全（§8.1）：窗口统计 / 端口会话聚合 / 流量分布
# ---------------------------------------------------------------------------
def network_insights(
    fields: List[Dict], rows: List[List[str]], logical_id: Optional[str] = None
) -> Dict[str, Any]:
    """网络场景洞察：核心指标、TOP 端口、协议分布、流量段分布。

    logical_id：数据集登记编码，必须由调用方传入（API 层传 dataset.logical_id）。
    未传入时正类判定一律为否，异常样本数恒为 0——不做任何自动推断（需求 6.4.1）。
    """
    cmap = _col_map(fields)

    i_dport = _pick_idx(cmap, "L4_DST_PORT")
    i_proto = _pick_idx(cmap, "PROTOCOL")
    i_in = _pick_idx(cmap, "IN_BYTES")
    i_retrans_in = _pick_idx(cmap, "RETRANSMITTED_IN_BYTES")
    i_label = _pick_idx(cmap, "Label", "class")

    total = len(rows)
    ports = _top_counts(
        [r[i_dport] for r in rows if i_dport is not None and i_dport < len(r)],
        top_n=10,
    )
    protos = _top_counts(
        [r[i_proto] for r in rows if i_proto is not None and i_proto < len(r)],
        top_n=8,
    )
    in_bytes = _col(rows, i_in) if i_in is not None else []
    retrans = _col(rows, i_retrans_in) if i_retrans_in is not None else []

    # 流量段分布（参照 §7.1 五段包长区间）
    segments = [0, 0, 0, 0, 0]
    for b in in_bytes:
        if b <= 128:
            segments[0] += 1
        elif b <= 256:
            segments[1] += 1
        elif b <= 512:
            segments[2] += 1
        elif b <= 1024:
            segments[3] += 1
        else:
            segments[4] += 1

    # 异常占比：正类判定只走显式登记表（DATASET_POSITIVE_LABELS，见 _label_is_risk），
    # 不再按标签字符串「非 0/normal 即异常」自动推断（需求 6.4.1）；
    # 未登记的数据集不计入异常（宁少报，不推断）。
    anomaly = 0
    if i_label is not None:
        for r in rows:
            if i_label < len(r) and r[i_label] not in ("", "?"):
                if _label_is_risk(logical_id, r[i_label]):
                    anomaly += 1

    return {
        "total_connections": total,
        "anomaly_count": anomaly,
        "anomaly_rate": round(anomaly / total, 4) if total else 0.0,
        "top_ports": ports,
        "protocol_distribution": protos,
        "flow_segments": {
            "labels": ["≤128", "129-256", "257-512", "513-1024", ">1024"],
            "counts": segments,
        },
        "avg_in_bytes": round(sum(in_bytes) / len(in_bytes), 2) if in_bytes else 0.0,
        "avg_retrans_in_bytes": round(sum(retrans) / len(retrans), 2) if retrans else 0.0,
    }


# ---------------------------------------------------------------------------
# 电力系统（§8.2）：电参量越限检测 / 设备健康度聚合
# ---------------------------------------------------------------------------
_POWER_LIMITS = {
    "VoltageLevel_kV": (0.0, 800.0),      # kV
    "CurrentAmp": (0.0, 3000.0),          # A
    "Temperature_C": (-20.0, 120.0),      # ℃
    "PowerFrequencyHz": (45.0, 55.0),     # Hz
}


def power_insights(fields: List[Dict], rows: List[List[str]]) -> Dict[str, Any]:
    """电力场景洞察：电参量均值/越限、设备健康度、IssueType 分布。"""
    cmap = _col_map(fields)
    i_component = _pick_idx(cmap, "Component")
    i_issue = _pick_idx(cmap, "IssueType")
    # (参量名, 下限, 上限, 列号)：列号在行循环外算一次，避免每行重复查列号
    limit_cols = [
        (name, lo, hi, _pick_idx(cmap, name))
        for name, (lo, hi) in _POWER_LIMITS.items()
    ]

    # 各电参量统计 + 越限计数
    params = {}
    for name, lo, hi, cidx in limit_cols:
        vals = _col(rows, cidx) if cidx is not None else []
        if vals:
            over = sum(1 for v in vals if v > hi)
            under = sum(1 for v in vals if v < lo)
            params[name] = {
                "mean": round(statistics.mean(vals), 2),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
                "violations": over + under,
                "violation_rate": round((over + under) / len(vals), 4),
            }

    # 设备健康度（§8.2：0-100 健康分，越限率越高分越低）
    device_viol = {}
    if i_component is not None:
        for i, r in enumerate(rows):
            comp = r[i_component] if i_component < len(r) else ""
            if not comp or comp in ("", "?"):
                continue
            dev = device_viol.setdefault(comp, {"total": 0, "violations": 0})
            dev["total"] += 1
            for _, lo, hi, cidx in limit_cols:
                if cidx is None or cidx >= len(r):
                    continue
                try:
                    v = float(r[cidx])
                except (TypeError, ValueError):
                    continue
                if v < lo or v > hi:
                    dev["violations"] += 1
    device_health = []
    for comp, d in device_viol.items():
        viol_rate = d["violations"] / (d["total"] * len(_POWER_LIMITS)) if d["total"] else 0
        score = max(0, round(100 * (1 - viol_rate), 1))
        device_health.append({"component": comp, "score": score, "violation_rate": round(viol_rate, 4), "samples": d["total"]})
    device_health.sort(key=lambda x: x["score"])

    issues = _top_counts([r[i_issue] for r in rows if i_issue is not None and i_issue < len(r)], top_n=8)

    return {
        "params": params,
        "device_health": device_health,
        "issue_distribution": issues,
    }


# ---------------------------------------------------------------------------
# 地质风险（§8.3）：地形因子合成 / 距离因子加权
# ---------------------------------------------------------------------------
def geological_insights(fields: List[Dict], rows: List[List[str]]) -> Dict[str, Any]:
    """地质场景洞察：关键地形因子统计与归一化叠加指数（0-100 易发性评分）。"""
    cmap = _col_map(fields)
    factor_names = [
        "Slope", "TWI", "Elevation", "Relief", "SPI", "Dis2roads", "Dis2fault", "Dis2river",
    ]
    factors = {}
    for name in factor_names:
        cidx = cmap.get(name)
        vals = _col(rows, cidx) if cidx is not None else []
        if vals:
            factors[name] = {
                "mean": round(statistics.mean(vals), 2),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
            }

    # 归一化叠加：把各因子 0-1 归一后等权求和 → 0-100 易发性（§8.3）
    scale = 100.0 / len(factors) if factors else 0.0
    contrib = {}
    for name, stats in factors.items():
        rng = stats["max"] - stats["min"]
        norm = (stats["mean"] - stats["min"]) / rng if rng > 0 else 0.5
        contrib[name] = round(norm * scale, 2)
    susceptibility = round(sum(contrib.values()), 1)

    return {
        "factors": factors,
        "factor_contribution": contrib,
        "susceptibility_score": susceptibility,
    }


# ---------------------------------------------------------------------------
# 航母甲板（§8.4）：轨迹时序特征 / 碰撞风险评分
# ---------------------------------------------------------------------------
#: 碰撞风险占位公式的参数：间距归一分母（m）、接近率归一分母（m/s）、两项权重
_COLLISION_DIST_SCALE = 100.0
_COLLISION_RATE_SCALE = 10.0
_COLLISION_WEIGHT_DIST = 0.6
_COLLISION_WEIGHT_RATE = 0.4


def carrier_insights(fields: List[Dict], rows: List[List[str]]) -> Dict[str, Any]:
    """航母甲板场景洞察：KPI（最小间距/接近率/总航程）、间距序列、方向角统计。"""
    cmap = _col_map(fields)
    i_min = _pick_idx(cmap, "inter_dist_min")
    i_change_mean = _pick_idx(cmap, "dist_change_mean_step", "dist_change_mean")
    i_plane1 = _pick_idx(cmap, "Plane1_dir_mean_deg")
    i_plane2 = _pick_idx(cmap, "Plane2_dir_mean_deg")
    i_total1 = _pick_idx(cmap, "Plane1_total_distance")
    i_total2 = _pick_idx(cmap, "Plane2_total_distance")

    min_dists = _col(rows, i_min) if i_min is not None else []
    changes = _col(rows, i_change_mean) if i_change_mean is not None else []
    p1 = _col(rows, i_plane1) if i_plane1 is not None else []
    p2 = _col(rows, i_plane2) if i_plane2 is not None else []
    t1 = _col(rows, i_total1) if i_total1 is not None else []
    t2 = _col(rows, i_total2) if i_total2 is not None else []

    min_dist = round(min(min_dists), 1) if min_dists else None
    approach_rate = round(abs(statistics.mean(changes)), 2) if changes else None

    # 碰撞风险评分（§8.4：最小间距越小、接近率越高 → 分越高，0-100 占位公式）
    score = 0
    if min_dist is not None and approach_rate is not None:
        dist_part = max(0.0, min(1.0, (_COLLISION_DIST_SCALE - min_dist) / _COLLISION_DIST_SCALE))
        rate_part = max(0.0, min(1.0, approach_rate / _COLLISION_RATE_SCALE))
        score = round(
            (_COLLISION_WEIGHT_DIST * dist_part + _COLLISION_WEIGHT_RATE * rate_part) * 100,
            1,
        )

    return {
        "min_inter_distance": min_dist,
        "approach_rate_ms": approach_rate,
        "collision_risk_score": score,
        "plane1_angle_stats": _angle_stats(p1),
        "plane2_angle_stats": _angle_stats(p2),
        "total_distance_plane1": round(t1[0], 1) if t1 else None,
        "total_distance_plane2": round(t2[0], 1) if t2 else None,
        "samples": len(rows),
    }


def _angle_stats(vals: List[float]) -> Dict[str, Any]:
    if not vals:
        return {"mean": None, "std": None, "max": None, "min": None}
    return {
        "mean": round(statistics.mean(vals), 1),
        "std": round(statistics.pstdev(vals), 1) if len(vals) > 1 else 0.0,
        "max": round(max(vals), 1),
        "min": round(min(vals), 1),
    }


# ---------------------------------------------------------------------------
# 统一入口：按场景分发（供 API 层调用）
# ---------------------------------------------------------------------------
def compute_scenario_insights(
    risk_type: str,
    fields: List[Dict],
    rows: List[List[str]],
    logical_id: Optional[str] = None,
) -> Dict[str, Any]:
    """按场景风险类型分发到各场景计算函数。未知场景返回空结构。

    logical_id 为数据集登记编码，透传给需要判定正类的场景洞察（当前仅网络场景），
    使正类口径唯一来自 ``constants.DATASET_POSITIVE_LABELS``。
    """
    if risk_type == RISK_TYPE_NETWORK:
        return {
            "scenario": "network",
            **network_insights(fields, rows, logical_id),
        }
    if risk_type == RISK_TYPE_POWER:
        return {"scenario": "power", **power_insights(fields, rows)}
    if risk_type == RISK_TYPE_GEOLOGICAL:
        return {"scenario": "geological", **geological_insights(fields, rows)}
    if risk_type == RISK_TYPE_FLIGHT_DECK:
        return {"scenario": "flightdeck", **carrier_insights(fields, rows)}
    return {"scenario": "unknown"}
