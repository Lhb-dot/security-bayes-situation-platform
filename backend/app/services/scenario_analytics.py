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
from typing import Any, Dict, List, Optional

from app.services.constants import (
    RISK_TYPE_FLIGHT_DECK,
    RISK_TYPE_GEOLOGICAL,
    RISK_TYPE_NETWORK,
    RISK_TYPE_POWER,
)


def _col_map(fields: List[Dict]) -> Dict[str, int]:
    """字段名 → 列号映射。"""
    return {f["name"]: i for i, f in enumerate(fields)}


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
    from collections import Counter

    cnt = Counter(v for v in values if v not in ("", "?"))
    return [{"value": k, "count": c} for k, c in cnt.most_common(top_n)]


# ---------------------------------------------------------------------------
# 网络安全（§8.1）：窗口统计 / 端口会话聚合 / 流量分布
# ---------------------------------------------------------------------------
def network_insights(fields: List[Dict], rows: List[List[str]]) -> Dict[str, Any]:
    """网络场景洞察：核心指标、TOP 端口、协议分布、流量段分布。"""
    cmap = _col_map(fields)

    def idx(*names):
        for n in names:
            if n in cmap:
                return cmap[n]
        return None

    i_dport = idx("L4_DST_PORT")
    i_proto = idx("PROTOCOL")
    i_in = idx("IN_BYTES")
    i_retrans_in = idx("RETRANSMITTED_IN_BYTES")
    i_label = idx("Label", "class")

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

    # 异常占比：标签列非 0（normal）视为异常样本（若有标签列）
    anomaly = 0
    if i_label is not None:
        for r in rows:
            if i_label < len(r) and r[i_label] not in ("", "?"):
                v = r[i_label]
                if v not in ("0", "normal"):
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

    def idx(name):
        return cmap.get(name)

    i_component = idx("Component")
    i_issue = idx("IssueType")

    # 各电参量统计 + 越限计数
    params = {}
    for name, (lo, hi) in _POWER_LIMITS.items():
        cidx = idx(name)
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
            for name, (lo, hi) in _POWER_LIMITS.items():
                cidx = idx(name)
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
def carrier_insights(fields: List[Dict], rows: List[List[str]]) -> Dict[str, Any]:
    """航母甲板场景洞察：KPI（最小间距/接近率/总航程）、间距序列、方向角统计。"""
    cmap = _col_map(fields)

    def idx(*names):
        for n in names:
            if n in cmap:
                return cmap[n]
        return None

    i_min = idx("inter_dist_min")
    i_change_mean = idx("dist_change_mean_step", "dist_change_mean")
    i_plane1 = idx("Plane1_dir_mean_deg")
    i_plane2 = idx("Plane2_dir_mean_deg")
    i_total1 = idx("Plane1_total_distance")
    i_total2 = idx("Plane2_total_distance")

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
        dist_part = max(0.0, min(1.0, (100.0 - min_dist) / 100.0))
        rate_part = max(0.0, min(1.0, approach_rate / 10.0))
        score = round((0.6 * dist_part + 0.4 * rate_part) * 100, 1)

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
    risk_type: str, fields: List[Dict], rows: List[List[str]]
) -> Dict[str, Any]:
    """按场景风险类型分发到各场景计算函数。未知场景返回空结构。"""
    if risk_type == RISK_TYPE_NETWORK:
        return {"scenario": "network", **network_insights(fields, rows)}
    if risk_type == RISK_TYPE_POWER:
        return {"scenario": "power", **power_insights(fields, rows)}
    if risk_type == RISK_TYPE_GEOLOGICAL:
        return {"scenario": "geological", **geological_insights(fields, rows)}
    if risk_type == RISK_TYPE_FLIGHT_DECK:
        return {"scenario": "flightdeck", **carrier_insights(fields, rows)}
    return {"scenario": "unknown"}
