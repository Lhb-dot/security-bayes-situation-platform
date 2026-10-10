"""首页聚合服务。

首页需要的是**页面级统计**（数据画像 / 运行态 / 我的工作台），而不是数据集预览或
风险事件分页列表。本服务按 `docs/首页字段口径说明.md` 的口径集中实现三类数据：

- 平台总览（最外层管理员首页）
- 场景数据画像（管理端场景首页）
- 我的工作台（场景用户首页，范围严格限定为「当前登录用户本人」）

## 口径硬约束（`docs/首页字段口径说明.md` 第三轮核查结论）

1. **有效样本量 / 有效数据集**：同源衍生文件（carrier 三份）只计一次，避免重复计数；
2. **风险样本占比**：按各数据集真实标签字段**全量**统计，不做分页截断（原「异常率」
   只读前 500 行导致恒 0）；
3. **风险分区间固定分箱** 0.5-0.7 / 0.7-0.9 / 0.9-1.0 —— 事件仅在判为风险时创建，
   分数恒 ≥0.5，故「<0.5」档恒空；
4. **高置信告警** = 按**当前账号**在该场景的高风险阈值判定为高风险的事件数
   （见 `app/services/risk_view.py`）。原先写死 `risk_score ≥ 0.8`，与账号阈值并存会导致
   同一页面上「高风险事件数」和「高置信告警数」用两套口径；生效阈值随 summary 的
   `high_threshold` 一并下发；
5. **离散区间字段**（ARFF 分箱值，如 `'(174.365-310.525]'`）取区间中点参与数值统计；
6. 地质场景**不存在「区域」字段**，改按真实字段 `Slope` 的坡度档位分组；
7. 用户端**不聚合他人数据**，后端按 `created_by_user_id` 强制过滤；
8. **风险等级一律按查看者阈值重算**，不读 `RiskEvent.risk_level` 这个落库的创建者视角值。
"""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import math
import os
import threading
import time
from statistics import mean, median, pstdev
from typing import Any, Iterable

from sqlalchemy import func, select

from app.models.algorithm import Algorithm
from app.models.app_user import AppUser
from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.risk_event import RiskEvent
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services import risk_view
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    ALGORITHM_STATUS_AVAILABLE,
    DATASET_POSITIVE_LABELS,
    DATASET_RISK_TYPES,
    DATASET_STATUS_ACTIVE,
    DATASET_VISIBILITY_COMPANY,
    DATASET_VISIBILITY_PERSONAL,
    DATASET_VISIBILITY_PLATFORM,
    dataset_display_name_of,
    is_risk_label,
    MODEL_STATUS_PUBLISHED,
    RISK_LEVEL_HIGH,
    RISK_EVENT_STATUS_PENDING,
    RISK_EVENT_STATUS_PROCESSING,
    RISK_EVENT_STATUS_RESOLVED,
    RISK_TYPE_FLIGHT_DECK,
    RISK_TYPE_GEOLOGICAL,
    RISK_TYPE_NETWORK,
    RISK_TYPE_POWER,
    ROLE_SCENARIO_ADMIN,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
)
from app.services.training_executor import resolve_dataset_path
from app.utils.arff_reader import (
    count_arff_rows,
    read_arff,
    read_arff_header,
    tally_arff_column,
)
from app.utils.common import row_to_dict

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 场景 code → 前端使用的稳定场景键（与页面分支一致）
SCENARIO_CODE_KEYS = {
    "network_security": "network",
    "power_system": "power",
    "flightdeck_operation": "flight_deck",
    "geological_risk": "geological",
}

#: 风险类型 → 场景键
RISK_TYPE_KEYS = {
    RISK_TYPE_NETWORK: "network",
    RISK_TYPE_POWER: "power",
    RISK_TYPE_FLIGHT_DECK: "flight_deck",
    RISK_TYPE_GEOLOGICAL: "geological",
}

#: 同源衍生的航母数据集；三份内容同源，统计时只保留一份（避免 3 倍重复计数）
CARRIER_LOGICAL_IDS = (
    "carrier_feature2_biaoqian",
    "carrier_feature2_lisan",
    "carrier_paired_trail",
)
#: 航母同源组的代表数据集：数值未离散化，可直接做数值统计
CARRIER_CANONICAL = "carrier_feature2_biaoqian"

#: 显式同源族 key：carrier 三份是**同一批样本的三种编码**（内容 MD5 各不相同），
#: 以及任何内容与其中一份完全相同的再注册（如 carrier_track_company_v1 = lisan）。
#: 只按内容指纹分组会把它们拆成 3~4 个组，因此必须保留显式族。
CARRIER_GROUP_ID = "carrier_shared_source"

#: NF-UNSW 数据集的 PROTOCOL 为协议号，映射为可读名称
PROTOCOL_NAMES = {"1": "ICMP", "6": "TCP", "17": "UDP", "47": "GRE", "50": "ESP", "89": "OSPF"}

#: 网络流量包长五段（NF-UNSW 的 NUM_PKTS_*_BYTES 五列）
FLOW_BUCKETS = (
    ("≤128B", "NUM_PKTS_UP_TO_128_BYTES"),
    ("128-256B", "NUM_PKTS_128_TO_256_BYTES"),
    ("256-512B", "NUM_PKTS_256_TO_512_BYTES"),
    ("512-1K", "NUM_PKTS_512_TO_1024_BYTES"),
    (">1K", "NUM_PKTS_1024_TO_1514_BYTES"),
)

#: 网络流量「统计维度」覆盖矩阵（D2）：(维度名, 稳定 key, 该维度的候选字段名)。
#: 数据集只要含该维度任一字段即算覆盖（实测 NF 有端口+包长、无 service；
#: KDD 有 service+flag、无端口包长 → 矩阵呈对角空白）。
NET_DIMENSIONS = (
    ("协议", "PROTOCOL", ("PROTOCOL",)),
    ("目的端口", "L4_DST_PORT", ("L4_DST_PORT", "L4_SRC_PORT")),
    ("包长分布", "NUM_PKTS_UP_TO_128_BYTES", ("NUM_PKTS_UP_TO_128_BYTES",)),
    ("连接状态", "flag", ("flag",)),
    ("应用服务", "service", ("service",)),
)

#: 事件状态
EVENT_STATUS_LABELS = {"PENDING": "待处置", "PROCESSING": "处理中", "RESOLVED": "已处置"}

#: 风险分固定分箱（下限由「只在判风险时建事件」决定，恒 ≥0.5）
SCORE_BINS = (("0.5-0.7", 0.5, 0.7), ("0.7-0.9", 0.7, 0.9), ("0.9-1.0", 0.9, 1.01))

#: 工作台「推理活动趋势」的统计窗口天数（前端标题需同步）
ACTIVITY_TREND_DAYS = 10

# 注：原 HIGH_CONFIDENCE = 0.8 已删除。它是写死的「高置信告警」线，与账号阈值并存
# 会导致同一页面上「高风险事件数」和「高置信告警数」用两套口径。
# 现在统一走 risk_view：按当前账号在该场景的高风险阈值判定，生效阈值随 summary 下发。

#: 地质地形因子（DIS_raw_data 真实字段）
GEO_FACTORS = ("Slope", "TWI", "Elevation", "Relief", "SPI", "Dis2roads", "Dis2fault", "Dis2river")

#: 地质数据集角色分工（D1）：logical_id → 角色名；未登记的角色为「未分类」。
#: 角色由数据集在场景家族中承担的结构性职责决定，与是否登记风险口径无关。
GEO_DATASET_ROLES = {
    "dis_raw_data": "因子表",
    "dis_landslides": "风险标签表",
    "dis_causative_factors": "致灾因子表",
    "dis_global_catalog": "全球编目表",
    "dis_guaruja_random": "随机基线集",
    # 生产 seed 用新 logical_id 注册的同一份 DIS_Landslides（字节完全相同，正常会被
    # 同源去重吸收）。此处登记是兜底：一旦它成为组代表，角色不能落到「未分类」。
    "geo_slope_company_v1": "风险标签表",
}
#: 未在 GEO_DATASET_ROLES 中登记的数据集统一角色
GEO_ROLE_UNCLASSIFIED = "未分类"

#: 电力电参量（PowerFrequencyHz 单列，其余做刻度条）
POWER_PARAMS = {
    "VoltageLevel_kV": "电压",
    "CurrentAmp": "电流",
    "Temperature_C": "温度",
    "PowerFrequencyHz": "频率",
    "Sensor_Packet_Loss_%": "遥测丢包率",
}
#: ARFF 中 `%` 可能被转义为 `\%`
POWER_PARAM_ALIASES = {"Sensor_Packet_Loss_%": ("Sensor_Packet_Loss_%", "Sensor_Packet_Loss_\\%")}

#: 事件侧电参量（与数据集侧同名字段）
POWER_EVENT_PARAMS = ("VoltageLevel_kV", "CurrentAmp", "Temperature_C", "PowerFrequencyHz")

#: 电参量单位（用于前端展示）
_POWER_UNITS = {
    "VoltageLevel_kV": "kV",
    "CurrentAmp": "A",
    "Temperature_C": "℃",
    "PowerFrequencyHz": "Hz",
    "Sensor_Packet_Loss_%": "%",
}

#: 电力数据集准入基线（与 frontend WorkspacePower.vue 的 NORMAL_BAND 一致）：
#: (字段名, 中文名, 下限, 上限)。下限为 None 表示只校验上限（丢包率 ≤1%）。
POWER_BASELINE = (
    ("VoltageLevel_kV", "电压", 300.0, 700.0),
    ("CurrentAmp", "电流", 400.0, 1600.0),
    ("Temperature_C", "温度", 30.0, 90.0),
    ("PowerFrequencyHz", "频率", 49.8, 50.2),
    ("Sensor_Packet_Loss_%", "遥测丢包率", None, 1.0),
)
#: 工频合格区间（PowerFrequencyHz），与 POWER_BASELINE 中的同名字段保持一致
POWER_FREQUENCY_BAND = (49.8, 50.2)

_QUOTES = "'\" \t\r\n"
_NUM_MISSING = {"", "?", "nan", "NaN", "none", "None", "null", "NULL"}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def _clean(value: Any) -> str:
    """去掉 ARFF 值两侧的引号与空白（`'Circuit Breaker'` → `Circuit Breaker`）。

    注：曾尝试「首尾无引号则跳过 strip」的快速分支，实测反而慢（CPython 的
    `str.strip()` 在无需裁剪时会原样返回，比额外的下标判断更便宜），已回退。
    """
    if value is None:
        return ""
    return str(value).strip().strip(_QUOTES).strip()


def _to_float(text: str) -> float | None:
    """解析有限浮点数；``inf`` / ``nan`` 一律视为缺失（ARFF 单边区间会用到）。"""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _mid_of_interval(text: str) -> float | None:
    """离散区间取代表值：`(a-b]` 取中点；单边区间 `(-inf-b]` / `(a-inf)` 取有限端点。"""
    if len(text) < 3 or text[0] not in "([" or text[-1] not in ")]":
        return None
    body = text[1:-1]
    if "-" not in body:
        return None
    low_text, _, high_text = body.rpartition("-")
    low, high = _to_float(low_text.strip()), _to_float(high_text.strip())
    if low is not None and high is not None:
        return (low + high) / 2
    return low if low is not None else high


def _num(value: Any) -> float | None:
    """把 ARFF 原始值转成数值。

    支持：普通数值（含负号/科学计数）、带引号数值、离散区间（取中点或有限端点）。
    缺失值（``?``、空、``inf`` 纯值）返回 None。

    热路径优化：数值列里绝大多数单元格是「首尾无引号无空白的数字字符串」，
    此时直接 `float()` 即可，跳过 `_clean()` 的三次 strip 与 `lower()`。
    实测 _num 单请求被调用 16 万次，这一跳省掉的是主要开销。

    等价性：首尾无引号/空白时 `_clean` 是恒等变换，故 `float(text)` 与
    `float(_clean(text))` 同值；`nan` / `inf` 经 `isfinite` 过滤后同样返回 None，
    与原来走 `_NUM_MISSING` / `"inf"` 判断的结果一致；非数值（含区间串）落入
    慢路径，行为不变。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value and value[0] not in _QUOTES and value[-1] not in _QUOTES:
        try:
            number = float(value)
        except ValueError:
            pass
        else:
            return number if math.isfinite(number) else None
    text = _clean(value)
    if text in _NUM_MISSING or "inf" == text.lower():
        return None
    direct = _to_float(text)
    if direct is not None:
        return direct
    return _mid_of_interval(text)


def _field_index(fields: list[dict]) -> dict[str, int]:
    return {_clean(field.get("name")): index for index, field in enumerate(fields)}


def _resolve_index(cmap: dict[str, int], names: Iterable[str]) -> int | None:
    """按候选名（含 ARFF 转义变体）解析字段下标。"""
    for name in names:
        if name in cmap:
            return cmap[name]
    return None


def _raw_values(rows: list[list[str]], index: int | None) -> list[str]:
    """取某列的非空原始值（去引号）。"""
    if index is None:
        return []
    result = []
    for row in rows:
        if index < len(row):
            text = _clean(row[index])
            if text and text != "?":
                result.append(text)
    return result


def _nums(rows: list[list[str]], index: int | None) -> list[float]:
    """取某列的全部可解析数值。"""
    if index is None:
        return []
    out = []
    for row in rows:
        if index < len(row):
            value = _num(row[index])
            if value is not None:
                out.append(value)
    return out


def _finite(nums: Iterable[float]) -> list[float]:
    """剔除 inf / nan，保证统计函数只处理有限值。"""
    return [value for value in nums if math.isfinite(value)]


def _mean(nums: list[float]) -> float | None:
    values = _finite(nums)
    return round(mean(values), 2) if values else None


def _stats(nums: list[float]) -> dict[str, Any] | None:
    """数值列统计：均值/最小/最大/中位/标准差。"""
    values = _finite(nums)
    if not values:
        return None
    return {
        "mean": round(mean(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "median": round(median(values), 2),
        "std": round(pstdev(values), 2),
        "range": round(max(values) - min(values), 2),
        "count": len(values),
    }


def _top(values: Iterable[Any], limit: int = 8) -> list[dict[str, Any]]:
    """分类计数 TOP N。"""
    return [{"value": value, "count": count} for value, count in Counter(values).most_common(limit)]


def _grouped_pairs(rows: list[list[str]], left_index: int | None, right_index: int | None) -> dict[str, list[str]]:
    """按左列分组收集右列原始值（用于「设备 × 问题类型」这类交叉统计）。"""
    grouped: dict[str, list[str]] = defaultdict(list)
    if left_index is None:
        return grouped
    for row in rows:
        if left_index >= len(row):
            continue
        key = _clean(row[left_index])
        if not key or key == "?":
            continue
        grouped[key].append(row[right_index] if right_index is not None and right_index < len(row) else "0")
    return grouped


def _label_is_risk(logical_id: str | None, value: Any) -> bool:
    """标签是否为正类（风险）—— 唯一口径来源是 ``constants.DATASET_POSITIVE_LABELS``。

    需求文档 §6.4.1 明令禁止按标签字符串 / 取值大小 / 文件排列顺序自动推断正类，
    因此这里**不再**使用「非 ``0/normal/no/false/none`` 即风险」的历史兜底规则
    （该规则对未登记数据集是"猜"，属违规实现），改为把判定完全委托给
    :func:`constants.is_risk_label`。未登记的数据集一律返回 ``False``（宁少报、不猜）；
    ``logical_id`` 缺失时同样返回 ``False``。
    """
    if not logical_id:
        return False
    return is_risk_label(logical_id, _clean(value))


def _risk_score(scores: list[float]) -> int:
    """场景风险分（0-100）：所辖风险事件 risk_score 的均值 ×100，无事件记 0。"""
    return round(mean(scores) * 100) if scores else 0


def _percent(part: int, total: int) -> float:
    """占比（0~1 小数）；分母为 0 记 0.0。

    0/0 在语义上是「无数据」而不是「零占比」，但本函数被**要求数值**的口径复用：
    ``_risk_level_of_rate`` 判档（前端 risk_level 契约只有 high/medium/low 三档）、
    平台总览 / 场景卡片的各风险占比（前端类型声明为 ``number``）。这些调用点
    不能接受 None，故 ``_percent`` 保持返回 0.0；需要区分「无数据 / 零占比」
    的字段改用 ``_percent_or_none``。
    """
    return round(part / total, 4) if total else 0.0


def _percent_or_none(part: int, total: int) -> float | None:
    """占比（0~1 小数）；分母为 0 返回 ``None``（下发 null）。

    用于「0/0 是未定义而非 0」的字段：数据集 risk_rate（文件缺失 / 空表）、
    工频合格率（无 PowerFrequencyHz 数据）、同源冗余率（无文件）。

    注意：前端 ``components/dashboard/dashFormat.ts`` 的 ``fmtPercent`` 用
    ``Number(value)`` 判有限性，而 ``Number(null) === 0``，**null 仍会渲染成
    「0.0%」**。要让「—」真正生效，需 F7 侧把 ``fmtPercent`` / ``fmtInt`` 改为
    ``value === null || value === undefined → '—'``（跨区提案 B1-P1）。
    本函数先把「未定义」这一事实如实下发，不伪造 0.0。
    """
    return round(part / total, 4) if total else None


def _label_kind(counts: Counter) -> str:
    """标签列形态（纯描述性，**不参与正类判定**）。

    - 去重取值集合为空 → ``"unknown"``；
    - 恰好 2 个取值 → ``"binary"``；
    - 多于 2 个且全部可转数值 → ``"numeric"``（如 landslides 的 {0..9, 11}）；
    - 多于 2 个且不可全转数值 → ``"multiclass"``（如 landslide_size 的 6 个规模档）。
    """
    values = [value for value in counts if value and value != "?"]
    if not values:
        return "unknown"
    if len(values) == 2:
        return "binary"
    if all(_to_float(value) is not None for value in values):
        return "numeric"
    return "multiclass" if len(values) > 2 else "unknown"


def _head_column_values(path: str, name: str, limit: int = 20) -> list[str]:
    """只读 ARFF 前 ``limit`` 行、取某列的非空原始值（不做全量解析）。

    供「编码形态」探测使用：只需看前 20 个值是否形如 ``'(a-b]'`` 区间串。
    """
    if not name or not os.path.exists(path):
        return []
    try:
        fields, rows = read_arff(path, max_rows=limit)
    except OSError:
        return []
    index = _field_index(fields).get(name)
    if index is None:
        return []
    values: list[str] = []
    for row in rows:
        if index >= len(row):
            continue
        text = _clean(row[index])
        if text and text != "?":
            values.append(text)
    return values


def _flight_encoding(fields: list[dict], path: str, label_field: str) -> str:
    """舰面数据集的编码形态：``paired`` / ``interval`` / ``numeric`` / ``unknown``。

    判定顺序（同契约 §5.3）：
    1. 字段名含 ``PlaneID1`` / ``PlaneID2`` → ``paired``（配对轨迹版）；
    2. ``inter_dist_min`` 的原始取值形如 ``'(a-b]'`` 区间串 → ``interval``（Weka 离散区间版）；
    3. 除标签列外全部字段类型为 ``numeric`` → ``numeric``（数值连续版）；
    4. 其余 → ``unknown``。

    注：第 3 条排除标签列。数值连续版（Feature2_Cleaning_biaoqian）除 ``Collision``
    这个 enum 标签列外全是 numeric，若把标签列也算进去会退化判定为 ``unknown``，
    与「数值连续 / 离散区间 / 配对轨迹」三形态的治理语义不符。
    """
    names = {field.get("name") for field in fields}
    if "PlaneID1" in names or "PlaneID2" in names:
        return "paired"
    if any(
        "(" in value or "]" in value
        for value in _head_column_values(path, "inter_dist_min")
    ):
        return "interval"
    feature_types = [
        str(field.get("type", "")).lower()
        for field in fields
        if _clean(field.get("name")) != _clean(label_field)
    ]
    if feature_types and all(field_type == "numeric" for field_type in feature_types):
        return "numeric"
    return "unknown"


def _power_baseline_violated(value: float | None, low: float | None, high: float | None) -> bool:
    """均值是否越出电力基线区间；无数据（None）不算越界。"""
    if value is None:
        return False
    if low is not None and value < low:
        return True
    if high is not None and value > high:
        return True
    return False


def _component_matrix_rows(
    buckets: dict[str, dict[str, list[str]]], kind: str
) -> list[dict[str, Any]]:
    """设备/系统 × 数据集 覆盖矩阵行（``buckets`` = 值 → {logical_id: 标签取值列表}）。

    只输出实际出现过的数据集（count > 0），按总样本量降序、同量按取值名升序。
    """
    rows: list[dict[str, Any]] = []
    for value, per_dataset in buckets.items():
        counts = []
        total = 0
        for logical_id, values in per_dataset.items():
            positives = sum(1 for item in values if _label_is_risk(logical_id, item))
            counts.append(
                {
                    "logical_id": logical_id,
                    "count": len(values),
                    "risk_rate": _percent(positives, len(values)),
                }
            )
            total += len(values)
        rows.append({"value": value, "kind": kind, "counts": counts, "_total": total})
    rows.sort(key=lambda row: (-row["_total"], row["value"]))
    for row in rows:
        row.pop("_total")
    return rows


# ---------------------------------------------------------------------------
# 场景风险等级：按「风险样本占比」判档
# ---------------------------------------------------------------------------
#
# 旧口径 `"high" if high_count else ...` 只看**有没有**高危事件：场景里存在 1 条就整体
# 标高危，与样本量、与风险占比都无关。实测四个场景全部落在高危，标签没有区分度。
#
# 现改为按 risk_sample_rate（风险样本量 / 有效样本量）判档。该值由 _effective_counts
# 全量统计数据集标签列得出，与卡片上「有效样本量」同源，口径自洽。
#
# 边界：无样本（分母为 0）时 _percent 返回 0.0 → 落到低危。这与旧口径的兜底一致，
# 不额外引入「无数据」等级（前端 risk_level 契约只有 high/medium/low 三档）。

#: 风险样本占比 >= 该值判为高危
SCENARIO_HIGH_RATE = 0.50
#: 风险样本占比 >= 该值判为中危；低于该值判为低危
SCENARIO_MEDIUM_RATE = 0.25


def _risk_level_of_rate(rate: float) -> str:
    """按风险样本占比判级（rate 为 0~1 的小数）。

    返回**小写**等级：本接口的对外契约一直是小写（改动前就是字面量 ``"high"``），
    与 ``risk_view`` 那套大写枚举不同，前端 ``Scenario.risk_level`` 按小写取值。
    """
    if rate >= SCENARIO_HIGH_RATE:
        return "high"
    if rate >= SCENARIO_MEDIUM_RATE:
        return "medium"
    return "low"


def _scenario_key(scenario_code: str | None, risk_type: str | None) -> str:
    return SCENARIO_CODE_KEYS.get(scenario_code or "") or RISK_TYPE_KEYS.get(risk_type or "") or "unknown"


# ---------------------------------------------------------------------------
# 数据集读取（进程级缓存）
# ---------------------------------------------------------------------------
#
# 原实现的缓存挂在 _DatasetReader 实例上，生命周期只有「一次请求」：首页 / 场景
# 中心每次刷新都要把所有 ARFF 重新解析一遍（实测 1.21s 里 1.11s 花在这里，占 90%），
# 且连续调用第二次依然一样慢。现改为**进程级**缓存，以文件 (mtime, size) 作为失效
# 依据 —— 数据集文件被替换 / 重新生成后签名变化，缓存自动重算。
#
# 内存约束：
# - 表头缓存、标签统计缓存、行数缓存都只有几十字节~几 KB，可放心常驻；
# - 全量行缓存（rows）单份可达数十 MB，因此用 LRU 限制条目数。

#: 全量行缓存的内存预算（字节），可用环境变量 DASHBOARD_ROW_CACHE_MB 调整。
#:
#: 实测 11 份数据集全量常驻真实占用约 81 MB，而 _estimate_rows_bytes 按 64 字节/
#: 单元格估算会得出约 122 MB（偏保守约 1.5 倍）。默认预算 192 MB 对应真实占用
#: 约 130 MB，既能让当前 11 份全部常驻（来回切场景不抖动），又有明确上界。
_ROW_CACHE_BUDGET = int(os.getenv("DASHBOARD_ROW_CACHE_MB", "192")) * 1024 * 1024

#: 进程级缓存锁：FastAPI 的同步端点跑在线程池中，缓存需要并发保护。
_CACHE_LOCK = threading.Lock()

#: dataset_id -> (mtime, size, fields)：只解析 @ATTRIBUTE 段，体积可忽略
_HEADER_CACHE: dict[int, tuple[float, int, list[dict]]] = {}

#: dataset_id -> (mtime, size, label_field, 总行数, 风险行数)
_LABEL_STATS_CACHE: dict[int, tuple[float, int, str, int, int]] = {}

#: dataset_id -> (mtime, size, 内容指纹)：同源去重的唯一依据，只依赖文件内容
_FINGERPRINT_CACHE: dict[int, tuple[float, int, str]] = {}

#: dataset_id -> (mtime, size, label_field, 标签列取值计数)：label_values / label_kind 用
_LABEL_VALUES_CACHE: dict[int, tuple[float, int, str, Counter]] = {}

#: dataset_id -> (mtime, size, 行数)
_ROW_COUNT_CACHE: dict[int, tuple[float, int, int]] = {}

#: dataset_id -> (mtime, size, fields, rows, 估算字节数)：按 _ROW_CACHE_BUDGET 淘汰
_ROW_CACHE: "OrderedDict[int, tuple[float, int, list[dict], list[list[str]], int]]" = OrderedDict()
_ROW_CACHE_BYTES = 0


def _file_signature(path: str) -> tuple[float, int]:
    """文件签名 (mtime, size)；文件不存在时返回 (0.0, -1)。"""
    try:
        stat = os.stat(path)
    except OSError:
        return (0.0, -1)
    return (stat.st_mtime, stat.st_size)


#: 内容指纹的分块大小：1 MB，避免大文件一次性读入内存
_FINGERPRINT_CHUNK = 1024 * 1024


def content_fingerprint(dataset: Dataset) -> str:
    """文件内容指纹：``"{size}-{sha1(全文)[:16]}"``；文件缺失返回 ``"missing:{logical_id}"``。

    同源去重的唯一依据。**不能**按 logical_id / 文件名判断同源——生产 seed 用新的
    logical_id 重新注册了同一批物理文件（net_flow_company_v1 = NF-UNSW-NB15-v2 …），
    只有内容哈希能识别出来。

    缓存与 ``_HEADER_CACHE`` / ``_LABEL_STATS_CACHE`` 同风格：以 ``_file_signature``
    的 (mtime, size) 作失效依据，进程级常驻（一份数据集只存一个 16 位摘要）。
    """
    path = resolve_dataset_path(dataset.file_path)
    mtime, size = _file_signature(path)
    with _CACHE_LOCK:
        cached = _FINGERPRINT_CACHE.get(dataset.id)
    if cached is not None and cached[0] == mtime and cached[1] == size:
        return cached[2]

    if size < 0:
        fingerprint = f"missing:{dataset.logical_id}"
    else:
        digest = hashlib.sha1()
        try:
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(_FINGERPRINT_CHUNK), b""):
                    digest.update(chunk)
        except OSError:
            fingerprint = f"missing:{dataset.logical_id}"
        else:
            fingerprint = f"{size}-{digest.hexdigest()[:16]}"

    with _CACHE_LOCK:
        _FINGERPRINT_CACHE[dataset.id] = (mtime, size, fingerprint)
    return fingerprint


def _estimate_rows_bytes(rows: list[list[str]]) -> int:
    """估算全量 rows 的内存占用（用于缓存淘汰，不要求精确）。

    以「单元格数 × 单个字符串均摊开销」估算。实测 38~74 字节/单元格，
    取 64 作为上界估计，宁可多算一点也不会撑爆预算。
    """
    cells = 0
    for row in rows:
        cells += len(row)
    return cells * 64 + len(rows) * 64


def warm_dataset_caches(db, max_seconds: float = 10.0) -> dict[str, Any]:
    """预热数据集缓存，让首个请求不必承担 ARFF 解析开销。

    由应用启动时的后台线程调用（见 ``app/main.py``）。按文件体积升序处理：
    小文件先缓存好，即使大文件中途超时，首页 / 场景中心依赖的统计也已就绪。
    累计耗时超过 ``max_seconds`` 立即停手，避免超大文件拖住启动流程。

    返回预热统计，供启动日志输出。
    """
    started = time.perf_counter()
    datasets = db.scalars(
        select(Dataset)
        .where(Dataset.status == DATASET_STATUS_ACTIVE)
        .order_by(Dataset.id)
    ).all()

    def _size(dataset: Dataset) -> int:
        return _file_signature(resolve_dataset_path(dataset.file_path))[1]

    reader = _DatasetReader()
    warmed = 0
    skipped = 0
    for dataset in sorted(datasets, key=_size):
        if time.perf_counter() - started > max_seconds:
            skipped = len(datasets) - warmed
            break
        try:
            reader.fields(dataset)      # 表头：定位标签列
            reader.label_stats(dataset)  # 标签统计：首页 / 场景中心
            reader.label_value_counts(dataset)  # 标签取值构成：数据画像 describe()
            content_fingerprint(dataset)  # 内容指纹：同源去重分组
            reader.rows(dataset)         # 全量行：数据画像 / 工作台
            warmed += 1
        except Exception:  # noqa: BLE001 - 预热失败不影响服务，跳过该数据集
            skipped += 1

    return {
        "total": len(datasets),
        "warmed": warmed,
        "skipped": skipped,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "row_cache_bytes": _ROW_CACHE_BYTES,
    }


def clear_dataset_caches() -> None:
    """清空全部数据集缓存。

    数据集登记 / 修改 / 删除后由 ``DatasetService`` 调用。缓存的常规失效依据是
    文件 (mtime, size) 与 label_field，本函数用于「元数据变了但文件签名没变」
    这类兜底场景（例如同名文件被同秒覆盖）。
    """
    global _ROW_CACHE_BYTES
    with _CACHE_LOCK:
        _HEADER_CACHE.clear()
        _LABEL_STATS_CACHE.clear()
        _FINGERPRINT_CACHE.clear()
        _LABEL_VALUES_CACHE.clear()
        _ROW_COUNT_CACHE.clear()
        _ROW_CACHE.clear()
        _ROW_CACHE_BYTES = 0


class _DatasetReader:
    """数据集读取器（进程级缓存）。

    - ``fields``      只读表头，用于定位标签列；
    - ``label_stats`` 走「只读标签列」快速路径，不物化其它列（实测 23x 提速），
      字段数校验失败时自动回退到 ``read_arff`` 全量解析；
    - ``rows``        全量解析（字段 + 数据行），供数据画像 / 工作台读取真实列值。
    """

    def _path(self, dataset: Dataset) -> str:
        return resolve_dataset_path(dataset.file_path)

    def fields(self, dataset: Dataset) -> list[dict]:
        """只解析 @ATTRIBUTE 段（与 read_arff 的 fields 结构一致）。"""
        path = self._path(dataset)
        mtime, size = _file_signature(path)
        with _CACHE_LOCK:
            cached = _HEADER_CACHE.get(dataset.id)
        if cached is not None and cached[0] == mtime and cached[1] == size:
            return cached[2]

        fields: list[dict] = []
        if os.path.exists(path):
            try:
                fields = read_arff_header(path)
            except OSError:
                fields = []
        with _CACHE_LOCK:
            _HEADER_CACHE[dataset.id] = (mtime, size, fields)
        return fields

    def rows(self, dataset: Dataset) -> tuple[list[dict], list[list[str]]]:
        """全量解析（字段 + 数据行），按内存预算做 LRU 缓存。"""
        global _ROW_CACHE_BYTES
        path = self._path(dataset)
        mtime, size = _file_signature(path)
        with _CACHE_LOCK:
            cached = _ROW_CACHE.get(dataset.id)
            if cached is not None and cached[0] == mtime and cached[1] == size:
                _ROW_CACHE.move_to_end(dataset.id)
                return cached[2], cached[3]

        fields: list[dict] = []
        rows: list[list[str]] = []
        if os.path.exists(path):
            try:
                fields, rows = read_arff(path, max_rows=None)
            except OSError:
                fields, rows = [], []
        weight = _estimate_rows_bytes(rows)

        with _CACHE_LOCK:
            previous = _ROW_CACHE.get(dataset.id)
            if previous is not None:
                _ROW_CACHE_BYTES -= previous[4]
            _ROW_CACHE[dataset.id] = (mtime, size, fields, rows, weight)
            _ROW_CACHE_BYTES += weight
            _ROW_CACHE.move_to_end(dataset.id)
            # 至少保留 1 份：单份超过预算时也要保证当前请求可复用
            while _ROW_CACHE_BYTES > _ROW_CACHE_BUDGET and len(_ROW_CACHE) > 1:
                _, evicted = _ROW_CACHE.popitem(last=False)
                _ROW_CACHE_BYTES -= evicted[4]
        return fields, rows

    def count(self, dataset: Dataset) -> int:
        """@DATA 段有效行数。"""
        path = self._path(dataset)
        mtime, size = _file_signature(path)
        with _CACHE_LOCK:
            cached = _ROW_COUNT_CACHE.get(dataset.id)
        if cached is not None and cached[0] == mtime and cached[1] == size:
            return cached[2]

        total = count_arff_rows(path) if os.path.exists(path) else 0
        with _CACHE_LOCK:
            _ROW_COUNT_CACHE[dataset.id] = (mtime, size, total)
        return total

    def label_stats(self, dataset: Dataset) -> tuple[int, int]:
        """（总行数, 风险行数）——按数据集真实标签字段全量统计。

        命中进程级缓存直接返回；未命中时优先走「只读标签列」快速路径，
        不可用（字段数校验失败）才回退到 read_arff 全量解析。
        """
        path = self._path(dataset)
        mtime, size = _file_signature(path)
        label_field = _clean(dataset.label_field)
        with _CACHE_LOCK:
            cached = _LABEL_STATS_CACHE.get(dataset.id)
        if (
            cached is not None
            and cached[0] == mtime
            and cached[1] == size
            and cached[2] == label_field
        ):
            return cached[3], cached[4]

        fields = self.fields(dataset)
        if not fields:
            # 与旧实现一致：没有表头（文件缺失 / 无 @ATTRIBUTE）时记 0，不去数行
            total = risk = 0
        else:
            index = _field_index(fields).get(label_field)
            if index is None:
                # 标签字段不在表头里：总行数照算，风险数记 0（与旧实现一致）
                total, risk = self.count(dataset), 0
            else:
                total, risk = self._tally_label(path, index, len(fields), dataset)

        with _CACHE_LOCK:
            _LABEL_STATS_CACHE[dataset.id] = (mtime, size, label_field, total, risk)
        return total, risk

    def _tally_label(
        self, path: str, index: int, expected_columns: int, dataset: Dataset
    ) -> tuple[int, int]:
        """只读标签列统计；快速路径不可用时回退到全量解析。"""
        if os.path.exists(path):
            try:
                tallied = tally_arff_column(path, index, expected_columns)
            except OSError:
                tallied = None
            if tallied is not None:
                rows, counter = tallied
                risk = sum(
                    count
                    for value, count in counter.items()
                    if _label_is_risk(dataset.logical_id, value)
                )
                return rows, risk

        _, rows = self.rows(dataset)
        return len(rows), sum(
            1
            for value in _raw_values(rows, index)
            if _label_is_risk(dataset.logical_id, value)
        )

    def label_value_counts(self, dataset: Dataset) -> Counter:
        """标签列取值计数（已去引号、已剔除缺失值）。

        与 ``label_stats`` 同款：命中进程级缓存直接返回；未命中优先走「只读标签列」
        快速路径（``tally_arff_column``），不可用才回退 ``read_arff`` 全量解析。
        **不做**正类判定——只描述取值构成（供 ``label_values`` / ``label_kind``）。
        """
        path = self._path(dataset)
        mtime, size = _file_signature(path)
        label_field = _clean(dataset.label_field)
        with _CACHE_LOCK:
            cached = _LABEL_VALUES_CACHE.get(dataset.id)
        if (
            cached is not None
            and cached[0] == mtime
            and cached[1] == size
            and cached[2] == label_field
        ):
            return cached[3]

        counter: Counter = Counter()
        fields = self.fields(dataset)
        if fields:
            index = _field_index(fields).get(label_field)
            if index is not None:
                tallied = None
                if os.path.exists(path):
                    try:
                        tallied = tally_arff_column(path, index, len(fields))
                    except OSError:
                        tallied = None
                if tallied is not None:
                    for value, count in tallied[1].items():
                        text = _clean(value)
                        if text and text != "?":
                            counter[text] += count
                else:
                    _, rows = self.rows(dataset)
                    counter = Counter(_raw_values(rows, index))

        with _CACHE_LOCK:
            _LABEL_VALUES_CACHE[dataset.id] = (mtime, size, label_field, counter)
        return counter

    def describe(self, dataset: Dataset, source_group: str | None = None) -> dict[str, Any]:
        """数据集资产明细行。

        ``source_group`` 由调用方按同源分组结果传入（``get_profile`` 一次算好，
        避免逐行重复分组）；缺省时按本数据集自身的同源键推导。
        """
        total, risk = self.label_stats(dataset)
        fields = self.fields(dataset)
        label_values = self.label_value_counts(dataset)
        uploaded_at = getattr(dataset, "uploaded_at", None)
        registered = dataset.logical_id in DATASET_RISK_TYPES
        return {
            "dataset_id": dataset.id,
            "logical_id": dataset.logical_id,
            "name": dataset_display_name_of(dataset),
            "version": dataset.version,
            "label_field": dataset.label_field,
            # 标签字段是否属于风险标签（dis_global_catalog 的 label 是灾害规模，不是风险标签）
            "is_risk_label": registered,
            "record_count": total,
            "risk_count": risk,
            # 空表 / 文件缺失时 0/0 是未定义，下发 null 而非误导性的 0.0
            "risk_rate": _percent_or_none(risk, total),
            # ---- 以下为管理员总览新增字段（只增不改，上方旧字段全部保留）----
            "attribute_count": len(fields),
            "field_names": [field.get("name") for field in fields],
            "visibility": dataset.visibility,
            "uploader_role": dataset.uploader_role,
            "uploaded_at": uploaded_at.isoformat() if uploaded_at else None,
            "source_group": source_group if source_group is not None else _group_key(dataset),
            "content_fingerprint": content_fingerprint(dataset),
            "positive_labels": sorted(DATASET_POSITIVE_LABELS.get(dataset.logical_id, set())),
            "label_values": [value for value, _ in label_values.most_common(12)],
            "label_kind": _label_kind(label_values),
            # 口径登记状态：与 is_risk_label 同值，语义更明确（未登记 → 不产风险事件）
            "caliber_registered": registered,
        }


def _group_key(dataset: Dataset) -> str:
    """单文件同源去重键：carrier 白名单归入显式同源族，其余按内容指纹。"""
    if dataset.logical_id in CARRIER_LOGICAL_IDS:
        return CARRIER_GROUP_ID
    return content_fingerprint(dataset)


def _effective_groups(datasets: list[Dataset]) -> dict[str, list[Dataset]]:
    """两遍分组：显式同源族（carrier）∪ 内容指纹。

    - 第一遍先取 carrier 三份的内容指纹集合：任何**内容与其中一份相同**的再注册
      （如 ``carrier_track_company_v1`` = ``Feature2_Cleaning_lisan``）都并入同一族，
      不允许单独成组；
    - 第二遍按「carrier 白名单 or 指纹命中 carrier 集合 → ``CARRIER_GROUP_ID``，
      否则用自身内容指纹」落组。

    不能只按指纹分组——carrier 三份是同一批样本的三种编码，内容各不相同
    （MD5 6296CCE2… / 1C95B0A5… / 77CB74B6…），只按指纹会被拆成 3 组。
    """
    carrier_fingerprints = {
        content_fingerprint(dataset)
        for dataset in datasets
        if dataset.logical_id in CARRIER_LOGICAL_IDS
    }
    groups: dict[str, list[Dataset]] = defaultdict(list)
    for dataset in datasets:
        fingerprint = content_fingerprint(dataset)
        # 白名单成员（logical_id ∈ CARRIER_LOGICAL_IDS）的指纹必然已在
        # carrier_fingerprints 中 —— 第一遍就是用同一批 datasets 算的，
        # 因此这里只按指纹判族，不必再单独判一次 logical_id（恒真的死分支）。
        key = CARRIER_GROUP_ID if fingerprint in carrier_fingerprints else fingerprint
        groups[key].append(dataset)
    return groups


def _representative(group: list[Dataset]) -> Dataset:
    """取同源组的代表数据集（优先数值未离散化的那份）。"""
    for dataset in group:
        if dataset.logical_id == CARRIER_CANONICAL:
            return dataset
    return group[0]


def _effective_counts(reader: _DatasetReader, datasets: list[Dataset]) -> tuple[int, int, int]:
    """去重口径的（有效样本量, 风险样本量, 有效数据集数）。"""
    groups = _effective_groups(datasets)
    samples = risk = 0
    for group in groups.values():
        total, positives = reader.label_stats(_representative(group))
        samples += total
        risk += positives
    return samples, risk, len(groups)


# ---------------------------------------------------------------------------
# 运行态（风险事件）聚合
# ---------------------------------------------------------------------------


def _event_scope(stmt, current_user, scenario_id: int | None = None):
    """按角色限定风险事件可见范围（需求 6.5.2 权限矩阵）。"""
    role = getattr(current_user, "role", None)
    if role == ROLE_SUPER_ADMIN:
        stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
            Dataset.visibility == DATASET_VISIBILITY_PLATFORM
        )
        if scenario_id is not None:
            stmt = stmt.where(RiskEvent.scenario_id == scenario_id)
    elif role == ROLE_SCENARIO_ADMIN:
        bound = getattr(current_user, "scenario_id", None)
        if scenario_id is not None and scenario_id != bound:
            raise ServiceError(403, "无权限操作")
        stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
            RiskEvent.scenario_id == bound,
            Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)),
        )
    else:
        stmt = stmt.where(RiskEvent.created_by_user_id == current_user.id)
        if scenario_id is not None:
            stmt = stmt.where(RiskEvent.scenario_id == scenario_id)
    return stmt


def _score_bins(events: list[RiskEvent]) -> list[dict[str, Any]]:
    buckets = {label: 0 for label, _, _ in SCORE_BINS}
    for event in events:
        score = float(event.risk_score or 0)
        for label, low, high in SCORE_BINS:
            if low <= score < high:
                buckets[label] += 1
                break
    return [{"label": label, "count": buckets[label]} for label, _, _ in SCORE_BINS]


def _daily_trend(events: list[RiskEvent], days: int = 7) -> list[dict[str, Any]]:
    """近 N 天事件趋势（occurred_at = 推理时间，代表使用量而非风险发生时间）。"""
    today = datetime.now(timezone.utc).date()
    window = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    buckets: dict[str, dict[str, int]] = {day.isoformat(): {"total": 0, "resolved": 0, "pending": 0} for day in window}
    for event in events:
        if not event.occurred_at:
            continue
        key = event.occurred_at.astimezone(timezone.utc).date().isoformat()
        if key not in buckets:
            continue
        buckets[key]["total"] += 1
        if event.status == RISK_EVENT_STATUS_RESOLVED:
            buckets[key]["resolved"] += 1
        else:
            buckets[key]["pending"] += 1
    return [{"date": day, **buckets[day]} for day in buckets]


def _event_summary(
    events: list[RiskEvent],
    days: int = 7,
    thresholds: dict | None = None,
    scenario_id: int | None = None,
) -> dict[str, Any]:
    """风险事件汇总。

    ``high_confidence`` 按**当前账号**在 ``scenario_id`` 的阈值判定（原先写死 0.8），
    并把生效阈值一并下发，前端据此渲染「风险分 ≥ x」的说明文字，避免文案与口径脱节。
    """
    status = {"PENDING": 0, "PROCESSING": 0, "RESOLVED": 0}
    today = datetime.now(timezone.utc).date()
    for event in events:
        if event.status in status:
            status[event.status] += 1
    scores = [float(event.risk_score or 0) for event in events]
    thresholds = thresholds or {}
    medium, high = risk_view.thresholds_for(thresholds, scenario_id)
    return {
        "total": len(events),
        "pending": status["PENDING"],
        "processing": status["PROCESSING"],
        "resolved": status["RESOLVED"],
        "today": sum(
            1
            for event in events
            if event.occurred_at and event.occurred_at.astimezone(timezone.utc).date() == today
        ),
        "high_confidence": sum(
            1 for event in events if risk_view.level_of(event, thresholds) == RISK_LEVEL_HIGH
        ),
        "high_threshold": high,
        "medium_threshold": medium,
        "avg_risk_score": round(mean(scores), 4) if scores else 0,
        "max_risk_score": round(max(scores), 4) if scores else 0,
        "score_bins": _score_bins(events),
        "status_funnel": [
            {"label": EVENT_STATUS_LABELS[key], "status": key, "count": value} for key, value in status.items()
        ],
        "daily_trend": _daily_trend(events, days),
    }


def _recent_event(event: RiskEvent, thresholds: dict | None = None) -> dict[str, Any]:
    data = row_to_dict(event)
    # risk_level 按查看者阈值重算（落库值是创建者视角）
    data["risk_level"] = risk_view.level_of(event, thresholds or {})
    data["risk_score"] = round(float(event.risk_score), 4) if event.risk_score is not None else None
    data["occurred_at"] = event.occurred_at.isoformat() if event.occurred_at else None
    return data


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DashboardService(ServiceBase):
    """首页聚合服务。"""

    # ------------------------------------------------------------------
    # ① 平台总览（最外层管理员）
    # ------------------------------------------------------------------
    @service_call
    def get_admin_overview(self, current_user):
        self.require_super_admin(current_user)
        reader = _DatasetReader()

        scenarios = self.db.scalars(select(Scenario).order_by(Scenario.id)).all()
        datasets = self.db.scalars(
            select(Dataset)
            .where(Dataset.status == DATASET_STATUS_ACTIVE, Dataset.visibility == DATASET_VISIBILITY_PLATFORM)
            .order_by(Dataset.id)
        ).all()

        # 全平台去重口径
        effective_samples, effective_risk, effective_datasets = _effective_counts(reader, datasets)

        published_models = self.db.scalar(
            select(func.count()).select_from(ModelVersion).where(ModelVersion.status == MODEL_STATUS_PUBLISHED)
        ) or 0
        algorithm_count = self.db.scalar(
            select(func.count()).select_from(Algorithm).where(Algorithm.status == ALGORITHM_STATUS_AVAILABLE)
        ) or 0
        inference_count = self.db.scalar(select(func.count()).select_from(InferenceRecord)) or 0
        user_count = self.db.scalar(select(func.count()).select_from(AppUser)) or 0
        events = self.db.scalars(_event_scope(select(RiskEvent), current_user)).all()

        # 逐场景的模型 / 已发布模型 / 推理记录计数：各用一次分组查询取回，
        # 避免在下面的场景循环里对每个场景各发 3 次 count（N+1）。
        model_count_by_scenario = {
            scenario_id: count
            for scenario_id, count in self.db.execute(
                select(ModelVersion.scenario_id, func.count()).group_by(ModelVersion.scenario_id)
            ).all()
        }
        published_by_scenario = {
            scenario_id: count
            for scenario_id, count in self.db.execute(
                select(ModelVersion.scenario_id, func.count())
                .where(ModelVersion.status == MODEL_STATUS_PUBLISHED)
                .group_by(ModelVersion.scenario_id)
            ).all()
        }
        inference_by_scenario = {
            scenario_id: count
            for scenario_id, count in self.db.execute(
                select(ModelVersion.scenario_id, func.count())
                .select_from(InferenceRecord)
                .join(ModelVersion, ModelVersion.id == InferenceRecord.model_version_id)
                .group_by(ModelVersion.scenario_id)
            ).all()
        }

        scenario_cards = []
        for scenario in scenarios:
            scene_datasets = [item for item in datasets if item.scenario_id == scenario.id]
            samples, risk, dataset_count = _effective_counts(reader, scene_datasets)
            scene_events = [event for event in events if event.scenario_id == scenario.id]
            scenario_cards.append(
                {
                    "scenario_id": scenario.id,
                    "code": scenario.code,
                    "scenario_key": _scenario_key(scenario.code, None),
                    "name": scenario.name,
                    "access_status": scenario.access_status,
                    # 去重口径：carrier 同源三份只计 1 个数据集
                    "dataset_count": dataset_count,
                    "effective_sample_count": samples,
                    "risk_count": risk,
                    "risk_rate": _percent(risk, samples),
                    "published_model_count": published_by_scenario.get(scenario.id, 0),
                    "model_count": model_count_by_scenario.get(scenario.id, 0),
                    "inference_count": inference_by_scenario.get(scenario.id, 0),
                    "event_count": len(scene_events),
                    "pending_count": sum(1 for event in scene_events if event.status == RISK_EVENT_STATUS_PENDING),
                }
            )

        return ok(
            data={
                "totals": {
                    "scenario_count": len(scenarios),
                    "effective_dataset_count": effective_datasets,
                    "effective_sample_count": effective_samples,
                    "risk_sample_count": effective_risk,
                    "risk_rate": _percent(effective_risk, effective_samples),
                    "algorithm_count": algorithm_count,
                    "published_model_count": published_models,
                    "inference_count": inference_count,
                    "risk_event_count": len(events),
                    "pending_event_count": sum(1 for event in events if event.status == RISK_EVENT_STATUS_PENDING),
                    "user_count": user_count,
                },
                "scenarios": scenario_cards,
                "runtime": {
                    "risk_event_count": len(events),
                    "pending_event_count": sum(1 for event in events if event.status == RISK_EVENT_STATUS_PENDING),
                    "processing_event_count": sum(1 for event in events if event.status == RISK_EVENT_STATUS_PROCESSING),
                    "resolved_event_count": sum(1 for event in events if event.status == RISK_EVENT_STATUS_RESOLVED),
                    "inference_count": inference_count,
                    "user_count": user_count,
                    "published_model_count": published_models,
                    "algorithm_count": algorithm_count,
                },
            }
        )

    # ------------------------------------------------------------------
    # ①' 场景中心卡片（场景列表页；任意登录用户，按角色限定可见场景）
    # ------------------------------------------------------------------
    @service_call
    def get_scenario_overview(self, current_user):
        """场景卡片聚合（场景中心列表页 + 平台运行总览共用，唯一数据源）。

        口径与平台总览完全一致（`docs/首页字段口径说明.md`），避免两处数字打架：
        - 数据集：同源衍生文件（carrier 三份）只计 1 个有效数据集；
        - 样本量：各有效数据集代表文件的全量样本数（不做前 N 行截断）；
        - 模型：仅统计 status=PUBLISHED 的已发布模型版本；
        - 风险分：所辖真实风险事件 risk_score 的均值 ×100（无事件记 0）；
        - 风险等级：有高危事件 high / 仅有中危 medium / 其余 low。

        前端「场景中心」与「平台运行总览」都消费本接口，不要再在前端自行
        按 `datasets.filter(...)` 计数（那条路径没有同源去重）。

        可见性（需求 6.5.2，与数据集中心 `DatasetService.get_list` 对齐）：
        - SUPER_ADMIN    ：全部场景，仅 platform 数据；
        - SCENARIO_ADMIN ：本人绑定场景，platform + company 数据；
        - SCENARIO_USER  ：本人绑定场景，platform + company + 本人 personal 数据。
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        bound = getattr(current_user, "scenario_id", None)
        user_id = getattr(current_user, "id", None)

        # ---- 可见场景 ----
        scenario_stmt = select(Scenario).order_by(Scenario.id)
        if role != ROLE_SUPER_ADMIN:
            if bound is None:
                return ok(
                    data={
                        "scenarios": [],
                        "totals": {
                            "scenario_count": 0,
                            "effective_dataset_count": 0,
                            "effective_sample_count": 0,
                            "published_model_count": 0,
                            "event_count": 0,
                            "high_risk_count": 0,
                            "risk_score": 0,
                            "risk_level": "low",
                        },
                    }
                )
            scenario_stmt = scenario_stmt.where(Scenario.id == bound)
        scenarios = self.db.scalars(scenario_stmt).all()

        # ---- 可见数据集 ----
        shared_visibility = (DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)
        dataset_stmt = select(Dataset).where(Dataset.status == DATASET_STATUS_ACTIVE)
        if role == ROLE_SUPER_ADMIN:
            dataset_stmt = dataset_stmt.where(Dataset.visibility == DATASET_VISIBILITY_PLATFORM)
        elif role == ROLE_SCENARIO_ADMIN:
            dataset_stmt = dataset_stmt.where(
                Dataset.scenario_id == bound,
                Dataset.visibility.in_(shared_visibility),
            )
        else:
            dataset_stmt = dataset_stmt.where(
                Dataset.scenario_id == bound,
                Dataset.visibility.in_(shared_visibility)
                | (
                    (Dataset.visibility == DATASET_VISIBILITY_PERSONAL)
                    & (Dataset.uploaded_by == user_id)
                ),
            )
        datasets = self.db.scalars(dataset_stmt.order_by(Dataset.id)).all()

        # ---- 已发布模型版本（一次分组查询，避免逐场景 N+1）----
        published_rows = self.db.execute(
            select(ModelVersion.scenario_id, func.count())
            .where(ModelVersion.status == MODEL_STATUS_PUBLISHED)
            .group_by(ModelVersion.scenario_id)
        ).all()
        published_by_scenario = {scenario_id: count for scenario_id, count in published_rows}

        reader = _DatasetReader()
        events = self.db.scalars(_event_scope(select(RiskEvent), current_user)).all()
        # 等级计数按当前账号阈值重算；level_of 内部按每条事件的 scenario_id 取本人该场景阈值
        thresholds = risk_view.load_thresholds(self.db, current_user)

        cards: list[dict[str, Any]] = []
        total_datasets = total_samples = total_models = total_events = total_high = total_risk = 0
        all_scores: list[float] = []
        for scenario in scenarios:
            scene_datasets = [item for item in datasets if item.scenario_id == scenario.id]
            samples, risk_samples, dataset_count = _effective_counts(reader, scene_datasets)
            scene_events = [event for event in events if event.scenario_id == scenario.id]
            high_count = sum(
                1 for event in scene_events if risk_view.level_of(event, thresholds) == RISK_LEVEL_HIGH
            )
            published = published_by_scenario.get(scenario.id, 0)
            scores = [float(event.risk_score or 0) for event in scene_events]
            # 场景等级判定依据：风险样本占比（与卡片「有效样本量」同源）
            risk_rate = _percent(risk_samples, samples)

            total_datasets += dataset_count
            total_samples += samples
            total_models += published
            total_events += len(scene_events)
            total_high += high_count
            total_risk += risk_samples
            all_scores.extend(scores)

            cards.append(
                {
                    "scenario_id": scenario.id,
                    "code": scenario.code,
                    "name": scenario.name,
                    "description": scenario.description or "",
                    "access_status": scenario.access_status,
                    "dataset_count": dataset_count,  # 去重口径
                    "sample_count": samples,  # 去重口径有效样本量
                    "risk_sample_count": risk_samples,
                    "risk_sample_rate": risk_rate,
                    "published_model_count": published,
                    "event_count": len(scene_events),
                    "high_risk_count": high_count,
                    # 风险分 = 该场景真实风险事件 risk_score 均值 ×100（无事件记 0）
                    "risk_score": _risk_score(scores),
                    "risk_level": _risk_level_of_rate(risk_rate),
                }
            )

        return ok(
            data={
                "scenarios": cards,
                "totals": {
                    "scenario_count": len(cards),
                    "effective_dataset_count": total_datasets,
                    "effective_sample_count": total_samples,
                    "published_model_count": total_models,
                    "event_count": total_events,
                    "high_risk_count": total_high,
                    "risk_score": _risk_score(all_scores),
                    "risk_level": _risk_level_of_rate(_percent(total_risk, total_samples)),
                },
            }
        )

    # ------------------------------------------------------------------
    # ② 场景数据画像（管理端：最外层管理员 / 场景管理员）
    # ------------------------------------------------------------------
    @service_call
    def get_profile(self, current_user, scenario_id: int):
        self.require_scenario_admin_of(current_user, scenario_id)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")

        stmt = select(Dataset).where(
            Dataset.scenario_id == scenario_id,
            Dataset.status == DATASET_STATUS_ACTIVE,
        )
        if getattr(current_user, "role", None) == ROLE_SUPER_ADMIN:
            stmt = stmt.where(Dataset.visibility == DATASET_VISIBILITY_PLATFORM)
        else:
            stmt = stmt.where(Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)))
        datasets = self.db.scalars(stmt.order_by(Dataset.id)).all()

        reader = _DatasetReader()
        groups = _effective_groups(datasets)
        # 同源组归属表：一次算好传给 describe，避免逐行重复分组
        source_group_of = {
            item.id: group_key for group_key, group in groups.items() for item in group
        }
        modeling = self._modeling_stats(datasets)
        samples, risk, dataset_count = _effective_counts(reader, datasets)
        risk_type = DATASET_RISK_TYPES.get(_representative(datasets).logical_id) if datasets else None
        key = _scenario_key(scenario.code, risk_type)

        data: dict[str, Any] = {
            "scenario_id": scenario_id,
            "scenario_code": scenario.code,
            "scenario_key": key,
            "scenario_name": scenario.name,
            "access_status": scenario.access_status,
            "risk_type": risk_type,
            "dataset_count": dataset_count,
            "dataset_file_count": len(datasets),
            "sample_count": samples,
            "risk_count": risk,
            "risk_rate": _percent(risk, samples),
            "datasets": [
                reader.describe(item, source_group_of.get(item.id)) for item in datasets
            ],
            "groups": [
                {
                    "group_id": group_key,
                    "datasets": [item.logical_id for item in group],
                    "record_count": reader.label_stats(_representative(group))[0],
                    "deduplicated": len(group) > 1,
                    # 同源组内文件数（>1 即存在同源冗余）与组指纹（= 组 key）
                    "file_count": len(group),
                    "fingerprint": group_key,
                }
                for group_key, group in groups.items()
            ],
            # 建模覆盖（数据白躺检测）：只统计当前可见数据集，无模型的数据集也出现且计 0
            "modeling": modeling,
        }

        by_logical = {item.logical_id: item for item in datasets}
        modeling_by_logical = {row["logical_id"]: row for row in modeling}
        if key == "network":
            data.update(self._network_profile(reader, by_logical))
        elif key == "power":
            data.update(self._power_profile(reader, by_logical))
        elif key == "flight_deck":
            data.update(
                self._flight_profile(reader, by_logical, modeling_by_logical)
            )
        elif key == "geological":
            data.update(
                self._geological_profile(reader, by_logical, modeling_by_logical)
            )
        return ok(data=data)

    def _modeling_stats(self, datasets: list[Dataset]) -> list[dict[str, Any]]:
        """建模覆盖：一次 group_by 查询拿到每个数据集的（已发布 / 草稿）模型数。

        用单条聚合查询而非逐数据集查询（禁止 N+1）。**只统计传入的可见数据集**；
        没有任何模型版本的数据集也会出现在结果里并计 0（「数据白躺」正是要看这个）。
        """
        if not datasets:
            return []
        rows = self.db.execute(
            select(
                ModelVersion.dataset_id,
                func.count(),
                func.count().filter(ModelVersion.status == MODEL_STATUS_PUBLISHED),
            )
            .where(ModelVersion.dataset_id.in_([item.id for item in datasets]))
            .group_by(ModelVersion.dataset_id)
        ).all()
        by_dataset = {dataset_id: (total, published) for dataset_id, total, published in rows}
        stats: list[dict[str, Any]] = []
        for item in datasets:
            total, published = by_dataset.get(item.id, (0, 0))
            stats.append(
                {
                    "logical_id": item.logical_id,
                    "published": published,
                    "draft": total - published,
                    "total": total,
                }
            )
        return stats

    @staticmethod
    def _dataset_columns(reader: _DatasetReader, item: Dataset | None) -> tuple[list[dict], list[list[str]]]:
        return reader.rows(item) if item is not None else ([], [])

    @classmethod
    def _network_profile(cls, reader: _DatasetReader, by_logical: dict[str, Dataset]) -> dict[str, Any]:
        """网络安全数据画像：NF-UNSW 提供协议/端口/包长/重传，KDD 提供 flag/service。"""
        nf_fields, nf_rows = cls._dataset_columns(reader, by_logical.get("nf_unsw_nb15_v2"))
        kdd_fields, kdd_rows = cls._dataset_columns(reader, by_logical.get("kdd_train_20_percent"))
        nf = _field_index(nf_fields)
        kdd = _field_index(kdd_fields)

        protocol_values = _raw_values(nf_rows, nf.get("PROTOCOL"))
        protocol_counts: Counter[str] = Counter()
        for value in protocol_values:
            protocol_counts[PROTOCOL_NAMES.get(value, f"Proto{value}")] += 1

        port_values = _raw_values(nf_rows, nf.get("L4_DST_PORT"))
        bucket_counts: list[dict[str, Any]] = []
        for label, column in FLOW_BUCKETS:
            total = sum(_nums(nf_rows, nf.get(column)))
            bucket_counts.append({"label": label, "value": round(total, 2)})

        in_bytes = _nums(nf_rows, nf.get("IN_BYTES"))
        retrans = _nums(nf_rows, nf.get("RETRANSMITTED_IN_BYTES"))
        avg_in, avg_retrans = _mean(in_bytes) or 0, _mean(retrans) or 0

        return {
            "protocol_distribution": [
                {"value": name, "count": count} for name, count in protocol_counts.most_common()
            ],
            "protocol_total": len(protocol_values),
            "distinct_port_count": len(set(port_values)),
            "top_ports": _top(port_values, 8),
            "flags": _top(_raw_values(kdd_rows, kdd.get("flag")), 8),
            "services": _top(_raw_values(kdd_rows, kdd.get("service")), 8),
            "flow_segments": bucket_counts,
            "traffic": {
                "avg_in_bytes": avg_in,
                "avg_retrans_in_bytes": avg_retrans,
                "retransmission_ratio": round(avg_retrans / avg_in, 4) if avg_in else 0,
                "in_bytes_stats": _stats(in_bytes),
                "retrans_stats": _stats(retrans),
            },
            "sources": {
                "traffic": "nf_unsw_nb15_v2",
                "connection": "kdd_train_20_percent",
                "protocol_note": "PROTOCOL 为协议号，已映射为 TCP/UDP/ICMP 等名称",
            },
            # ---- D1：数据集风险口径可比性矩阵（每数据集一行，同口径并列）----
            "caliber_matrix": cls._network_caliber_matrix(reader, by_logical),
            # ---- D2：统计维度覆盖矩阵（每维度一行，列出覆盖的数据集）----
            "dimension_coverage": cls._network_dimension_coverage(reader, by_logical),
        }

    @classmethod
    def _network_caliber_matrix(
        cls, reader: _DatasetReader, by_logical: dict[str, Dataset]
    ) -> list[dict[str, Any]]:
        """D1：各数据集「风险口径」横向对比行。

        ``deviation`` = 本数据集风险占比 ÷ 场景合并风险占比（场景占比为 0 时记 None），
        即该数据集的「风险语言」相对场景合并口径高/低多少倍。
        """
        samples, risk, _ = _effective_counts(reader, list(by_logical.values()))
        scene_rate = _percent(risk, samples)
        matrix: list[dict[str, Any]] = []
        for item in by_logical.values():
            info = reader.describe(item)
            rate = info["risk_rate"]
            matrix.append(
                {
                    "logical_id": info["logical_id"],
                    "name": info["name"],
                    "label_field": info["label_field"],
                    "positive_labels": info["positive_labels"],
                    "label_values": info["label_values"],
                    "label_kind": info["label_kind"],
                    "record_count": info["record_count"],
                    "risk_count": info["risk_count"],
                    "risk_rate": rate,
                    # rate 为 None（该数据集空表 / 文件缺失）时偏离度无法计算
                    "deviation": round(rate / scene_rate, 4) if rate is not None and scene_rate else None,
                    "registered": info["caliber_registered"],
                }
            )
        return matrix

    @classmethod
    def _network_dimension_coverage(
        cls, reader: _DatasetReader, by_logical: dict[str, Dataset]
    ) -> list[dict[str, Any]]:
        """D2：统计维度 → 覆盖数据集列表（矩阵里成对角空白的正是覆盖缺口）。"""
        indexes = {
            item.logical_id: _field_index(reader.fields(item))
            for item in by_logical.values()
        }
        coverage: list[dict[str, Any]] = []
        for dimension, dimension_key, names in NET_DIMENSIONS:
            coverage.append(
                {
                    "dimension": dimension,
                    "key": dimension_key,
                    "datasets": [
                        logical_id
                        for logical_id, cmap in indexes.items()
                        if any(name in cmap for name in names)
                    ],
                }
            )
        return coverage

    @classmethod
    def _power_profile(cls, reader: _DatasetReader, by_logical: dict[str, Dataset]) -> dict[str, Any]:
        """电力系统数据画像：电参量、设备/系统/问题分布、设备故障率、遥测基线与覆盖矩阵。

        - **旧字段**（``params``/``fault_count``/``device_fault_rates`` …）改为在
          ``by_logical`` 上按「同源去重后的代表数据集」合并统计：不再硬编码单个
          ``logical_id``，同时避免把同源副本重复求和（power 场景两份文件内容相同）。
        - **新字段** ``telemetry_by_dataset`` / ``component_matrix`` 按数据集逐个展开，
          用于横向对比各注册数据是否同质。
        """
        groups = _effective_groups(list(by_logical.values()))
        representatives = [_representative(group) for group in groups.values()]
        rep_columns = [
            (item, *cls._dataset_columns(reader, item)) for item in representatives
        ]

        params: list[dict[str, Any]] = []
        for column, label in POWER_PARAMS.items():
            values: list[float] = []
            for _item, fields, rows in rep_columns:
                cmap = _field_index(fields)
                index = _resolve_index(cmap, POWER_PARAM_ALIASES.get(column, (column,)))
                values.extend(_nums(rows, index))
            params.append(
                {
                    "name": label,
                    "key": column,
                    "unit": _POWER_UNITS.get(column, ""),
                    "stats": _stats(values),
                }
            )

        device_buckets: dict[str, list[str]] = defaultdict(list)
        # 每个设备/系统的正类计数：按**该数据集自己的**显式登记表判定（§6.4.1）
        device_risk: dict[str, int] = defaultdict(int)
        issue_values: list[str] = []
        component_values: list[str] = []
        system_values: list[str] = []
        target_values: list[str] = []
        fault_count = 0
        for _item, fields, rows in rep_columns:
            cmap = _field_index(fields)
            component_index = cmap.get("Component")
            target_index = cmap.get("Target_Event")
            for component, values in _grouped_pairs(rows, component_index, target_index).items():
                device_buckets[component].extend(values)
                device_risk[component] += sum(
                    1 for value in values if _label_is_risk(_item.logical_id, value)
                )
            issue_values.extend(_raw_values(rows, cmap.get("IssueType")))
            component_values.extend(_raw_values(rows, component_index))
            system_values.extend(_raw_values(rows, cmap.get("SystemName")))
            target_values.extend(_raw_values(rows, target_index))
            fault_count += sum(
                1
                for value in _raw_values(rows, target_index)
                if _label_is_risk(_item.logical_id, value)
            )

        device_rates = []
        for component, values in device_buckets.items():
            positives = device_risk[component]
            device_rates.append(
                {
                    "value": component,
                    "count": len(values),
                    "risk_count": positives,
                    "risk_rate": _percent(positives, len(values)),
                }
            )

        return {
            "params": params,
            "fault_count": fault_count,
            "fault_rate": _percent(fault_count, len(target_values)),
            "issues": _top(issue_values, 8),
            "components": _top(component_values, 8),
            "systems": _top(system_values, 8),
            "device_fault_rates": sorted(device_rates, key=lambda item: item["risk_rate"], reverse=True),
            "sources": {"dataset": "powergrid_knowledgebase"},
            # ---- D1：逐数据集遥测画像 + 准入基线校验 ----
            "telemetry_by_dataset": cls._power_telemetry_by_dataset(reader, by_logical),
            # ---- D2：设备/系统 × 数据集 覆盖矩阵 ----
            "component_matrix": cls._power_component_matrix(reader, by_logical),
        }

    @classmethod
    def _power_telemetry_by_dataset(
        cls, reader: _DatasetReader, by_logical: dict[str, Dataset]
    ) -> list[dict[str, Any]]:
        """D1：每个可见数据集一行遥测画像。

        ``params`` 只给均值（刻度条用），``frequency_pass_rate`` 是工频落在
        ``POWER_FREQUENCY_BAND`` 内的样本比例，``baseline_ok`` / ``violations``
        按 ``POWER_BASELINE`` 逐项校验均值是否越界（无数据的项不算越界）。
        """
        rows_out: list[dict[str, Any]] = []
        for item in by_logical.values():
            fields, rows = cls._dataset_columns(reader, item)
            cmap = _field_index(fields)
            total, _risk = reader.label_stats(item)

            row_params: list[dict[str, Any]] = []
            means: dict[str, float | None] = {}
            for column, label in POWER_PARAMS.items():
                index = _resolve_index(cmap, POWER_PARAM_ALIASES.get(column, (column,)))
                value = _mean(_nums(rows, index))
                means[column] = value
                row_params.append(
                    {
                        "key": column,
                        "name": label,
                        "unit": _POWER_UNITS.get(column, ""),
                        "mean": value,
                    }
                )

            frequency_index = _resolve_index(
                cmap, POWER_PARAM_ALIASES.get("PowerFrequencyHz", ("PowerFrequencyHz",))
            )
            frequency_values = _nums(rows, frequency_index)
            low, high = POWER_FREQUENCY_BAND
            passed = sum(1 for value in frequency_values if low <= value <= high)
            violations = [
                label
                for column, label, base_low, base_high in POWER_BASELINE
                if _power_baseline_violated(means.get(column), base_low, base_high)
            ]

            rows_out.append(
                {
                    "logical_id": item.logical_id,
                    "name": dataset_display_name_of(item),
                    "record_count": total,
                    "params": row_params,
                    # 无 PowerFrequencyHz 数据时合格率未定义 → null
                    "frequency_pass_rate": _percent_or_none(passed, len(frequency_values)),
                    "packet_loss_mean": means.get("Sensor_Packet_Loss_%"),
                    "baseline_ok": not violations,
                    "violations": violations,
                }
            )
        return rows_out

    @classmethod
    def _power_component_matrix(
        cls, reader: _DatasetReader, by_logical: dict[str, Dataset]
    ) -> list[dict[str, Any]]:
        """D2：设备 / 系统 × 数据集 的样本量与风险占比矩阵。

        先输出 ``kind="component"`` 的设备行，再输出 ``kind="system"`` 的系统行；
        每行只列实际覆盖到该设备/系统的数据集（count > 0）。
        """
        by_component: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        by_system: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for item in by_logical.values():
            fields, rows = cls._dataset_columns(reader, item)
            cmap = _field_index(fields)
            target_index = cmap.get("Target_Event")
            for component, values in _grouped_pairs(rows, cmap.get("Component"), target_index).items():
                by_component[component][item.logical_id].extend(values)
            for system, values in _grouped_pairs(rows, cmap.get("SystemName"), target_index).items():
                by_system[system][item.logical_id].extend(values)
        return _component_matrix_rows(by_component, "component") + _component_matrix_rows(
            by_system, "system"
        )

    @classmethod
    def _flight_profile(
        cls,
        reader: _DatasetReader,
        by_logical: dict[str, Dataset],
        modeling_by_logical: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """舰面调度数据画像：以去重后的载体数据集为准（同源三份只算一份）。"""
        item = by_logical.get(CARRIER_CANONICAL) or next(iter(by_logical.values()), None)
        fields, rows = cls._dataset_columns(reader, item)
        cmap = _field_index(fields)

        collision_index = cmap.get("Collision")
        distance_index = cmap.get("inter_dist_min")
        collision_values = _raw_values(rows, collision_index)
        collision_count = sum(
            1 for value in collision_values if _label_is_risk(item.logical_id, value)
        )

        distance_curve = []
        for step in range(1, 51):
            values = _nums(rows, cmap.get(f"inter_distance_{step}"))
            distance_curve.append({"step": step, "mean": _mean(values)})

        # 碰撞 vs 正常 最小间距对比：逐行同时解析标签与最小间距，保证同一样本对齐
        paired: list[tuple[bool, float]] = []
        if collision_index is not None and distance_index is not None:
            for row in rows:
                if collision_index >= len(row) or distance_index >= len(row):
                    continue
                value = _num(row[distance_index])
                if value is not None:
                    paired.append(
                        (_label_is_risk(item.logical_id, row[collision_index]), value)
                    )

        comparison = {}
        for label, want_risk in (("collision", True), ("normal", False)):
            values = [value for flag, value in paired if flag == want_risk]
            comparison[label] = {"count": len(values), "mean_min_distance": _mean(values)}

        return {
            "collision_count": collision_count,
            "collision_rate": _percent(collision_count, len(collision_values)),
            "distance": {
                "min": _stats(_nums(rows, cmap.get("inter_dist_min"))),
                "mean": _stats(_nums(rows, cmap.get("inter_dist_mean"))),
                "median": _stats(_nums(rows, cmap.get("inter_dist_median"))),
                "std": _stats(_nums(rows, cmap.get("inter_dist_std"))),
                "range": _stats(_nums(rows, cmap.get("inter_dist_range"))),
            },
            "approach": {
                "abs_change_ratio_mean": _mean([abs(value) for value in _nums(rows, cmap.get("dist_change_ratio"))]),
                "change_ratio_mean": _mean(_nums(rows, cmap.get("dist_change_ratio"))),
            },
            "total_distance": {
                "plane1_mean": _mean(_nums(rows, cmap.get("Plane1_total_distance"))),
                "plane2_mean": _mean(_nums(rows, cmap.get("Plane2_total_distance"))),
                "diff_mean": _mean(_nums(rows, cmap.get("total_dist_diff"))),
            },
            "direction": {
                "plane1": {
                    "mean": _mean(_nums(rows, cmap.get("Plane1_dir_mean_deg"))),
                    "std": _mean(_nums(rows, cmap.get("Plane1_dir_std_deg"))),
                    "stats": _stats(_nums(rows, cmap.get("Plane1_dir_mean_deg"))),
                },
                "plane2": {
                    "mean": _mean(_nums(rows, cmap.get("Plane2_dir_mean_deg"))),
                    "std": _mean(_nums(rows, cmap.get("Plane2_dir_std_deg"))),
                    "stats": _stats(_nums(rows, cmap.get("Plane2_dir_mean_deg"))),
                },
            },
            "relative_angle": {
                "mean": _mean(_nums(rows, cmap.get("relative_angle_mean_deg"))),
                "max": _mean(_nums(rows, cmap.get("relative_angle_max_deg"))),
            },
            "distance_curve": distance_curve,
            "collision_comparison": comparison,
            "sources": {
                "dataset": item.logical_id if item is not None else None,
                "note": "carrier 三份为同源衍生，本页只按其中一份统计，避免 3 倍重复计数",
            },
            # ---- D1：同源编码族（每份文件一行，标注编码形态与一致性）----
            "encoding_family": cls._flight_encoding_family(
                reader, by_logical, modeling_by_logical
            ),
            # ---- D2：冗余度（文件数 vs 有效组数）----
            "redundancy": cls._flight_redundancy(reader, by_logical),
        }

    @classmethod
    def _flight_encoding_family(
        cls,
        reader: _DatasetReader,
        by_logical: dict[str, Dataset],
        modeling_by_logical: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """D1：同源编码族的逐文件画像。

        ``encoding`` 由字段结构判定（paired / interval / numeric / unknown），
        ``collision_consistent`` = 本文件风险样本数与同源组代表文件是否一致
        （不一致说明「同一批样本的另一种编码」标签对不上，需要治理）。
        """
        modeling_by_logical = modeling_by_logical or {}
        groups = _effective_groups(list(by_logical.values()))
        source_group_of = {
            entry.id: group_key for group_key, group in groups.items() for entry in group
        }
        representative_risk = {
            group_key: reader.label_stats(_representative(group))[1]
            for group_key, group in groups.items()
        }
        family: list[dict[str, Any]] = []
        for entry in by_logical.values():
            entry_fields = reader.fields(entry)
            total, risk = reader.label_stats(entry)
            group_key = source_group_of.get(entry.id) or _group_key(entry)
            modeling = modeling_by_logical.get(entry.logical_id) or {}
            family.append(
                {
                    "logical_id": entry.logical_id,
                    "name": dataset_display_name_of(entry),
                    "source_group": group_key,
                    "encoding": _flight_encoding(
                        entry_fields,
                        resolve_dataset_path(entry.file_path),
                        entry.label_field,
                    ),
                    "attribute_count": len(entry_fields),
                    "record_count": total,
                    "risk_count": risk,
                    "collision_consistent": risk == representative_risk.get(group_key),
                    "published_model_count": modeling.get("published", 0),
                }
            )
        return family

    @classmethod
    def _flight_redundancy(
        cls, reader: _DatasetReader, by_logical: dict[str, Dataset]
    ) -> dict[str, Any]:
        """D2：冗余度 = 1 - 有效同源组数 / 文件数；同时给出原始与去重后样本量。"""
        groups = _effective_groups(list(by_logical.values()))
        file_count = len(by_logical)
        effective_group_count = len(groups)
        raw_samples = sum(reader.label_stats(entry)[0] for entry in by_logical.values())
        deduped_samples = sum(
            reader.label_stats(_representative(group))[0] for group in groups.values()
        )
        return {
            "file_count": file_count,
            "effective_group_count": effective_group_count,
            # 无文件时冗余率未定义 → null，避免与真实的「零冗余」混淆
            "redundancy_rate": (
                round(1 - effective_group_count / file_count, 4) if file_count else None
            ),
            "raw_samples": raw_samples,
            "deduped_samples": deduped_samples,
        }

    @classmethod
    def _geological_profile(
        cls,
        reader: _DatasetReader,
        by_logical: dict[str, Dataset],
        modeling_by_logical: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """地质风险数据画像：主集地形因子 + 各数据集标签 + 全球灾害目录分类。

        另输出「数据集角色分工」（roles）与「因子覆盖/分箱一致性」（factor_coverage），
        用于回答「这一族异构数据集各自承担什么职责、哪些因子能横向对齐」。
        """
        main = by_logical.get("dis_raw_data")
        main_fields, main_rows = cls._dataset_columns(reader, main)
        cmap = _field_index(main_fields)

        factors = []
        for name in GEO_FACTORS:
            stats = _stats(_nums(main_rows, cmap.get(name)))
            factors.append({"value": name, "stats": stats, "mean": (stats or {}).get("mean")})

        catalog_item = by_logical.get("dis_global_catalog")
        catalog_fields, catalog_rows = cls._dataset_columns(reader, catalog_item)
        catalog = _field_index(catalog_fields)
        catalog_distribution = {
            "trigger": _top(_raw_values(catalog_rows, catalog.get("landslide_trigger")), 8),
            "category": _top(_raw_values(catalog_rows, catalog.get("landslide_category")), 8),
            "size": _top(_raw_values(catalog_rows, catalog.get("landslide_size")), 6),
            "country": _top(_raw_values(catalog_rows, catalog.get("country_name")), 8),
        }

        modeling_by_logical = modeling_by_logical or {}

        # 同源去重：同一份物理文件被多次注册时（如 geo_slope_company_v1 ≡ dis_landslides，
        # 字节完全相同）只保留第一个。否则角色矩阵会多出一行同名同内容的数据集，
        # 因子覆盖矩阵也会把同一个来源算两次。D1/D2 共用这一份基底。
        unique_entries: list[Dataset] = []
        seen_fingerprints: set[str] = set()
        for entry in by_logical.values():
            fingerprint = content_fingerprint(entry)
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            unique_entries.append(entry)

        roles: list[dict[str, Any]] = []
        for entry in unique_entries:
            info = reader.describe(entry)
            modeling = modeling_by_logical.get(entry.logical_id) or {}
            roles.append(
                {
                    "logical_id": entry.logical_id,
                    "name": info["name"],
                    "role": GEO_DATASET_ROLES.get(entry.logical_id, GEO_ROLE_UNCLASSIFIED),
                    "attribute_count": info["attribute_count"],
                    "label_field": info["label_field"],
                    "label_kind": info["label_kind"],
                    # 是否有任何模型版本引用（含草稿）——「数据白躺」判定
                    "participates_in_training": modeling.get("total", 0) > 0,
                    # 是否登记为风险口径（未登记 → 不产风险事件，如 dis_global_catalog）
                    "produces_risk_events": info["caliber_registered"],
                    "record_count": info["record_count"],
                    "risk_rate": info["risk_rate"],
                }
            )

        factor_coverage: list[dict[str, Any]] = []
        for factor in GEO_FACTORS:
            covered: list[str] = []
            definitions: list[tuple] = []
            for entry in unique_entries:
                for field in reader.fields(entry):
                    # 大小写无关：guaruja_random 的字段全是小写（twi / slope / elevation），
                    # 与 GEO_FACTORS 的大写写法同义（scenario_feature_catalog 的 names 里
                    # 两种写法都已登记）。精确匹配会把它们整批漏掉，低估覆盖度。
                    if _clean(field.get("name")).lower() == factor.lower():
                        covered.append(entry.logical_id)
                        definitions.append(tuple(field.get("enum_values") or ()))
                        break
            factor_coverage.append(
                {
                    "factor": factor,
                    "datasets": covered,
                    # 只有 0/1 个数据集含该因子时视为一致（无可比对象）
                    "consistent_binning": len(set(definitions)) <= 1,
                }
            )

        return {
            "factors": factors,
            "factor_count": sum(1 for item in factors if item["stats"]),
            "catalog_distribution": catalog_distribution,
            "sources": {
                "factors": "dis_raw_data",
                "catalog": "dis_global_catalog",
                "note": "数据集无「区域」字段，坡度相关口径一律按真实字段 Slope 分档",
            },
            # ---- D1：数据集角色分工 ----
            "roles": roles,
            # ---- D2：因子覆盖与分箱一致性 ----
            "factor_coverage": factor_coverage,
        }

    # ------------------------------------------------------------------
    # ③ 我的工作台（场景用户；管理端亦可用，范围按角色收窄）
    # ------------------------------------------------------------------
    @service_call
    def get_workspace(self, current_user, scenario_id: int):
        self.require_scenario_access(current_user, scenario_id)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")

        stmt = _event_scope(
            select(RiskEvent).where(RiskEvent.scenario_id == scenario_id), current_user, scenario_id
        )
        events = self.db.scalars(stmt.order_by(RiskEvent.occurred_at.desc())).all()
        # 风险等级/高风险计数按当前账号在该场景的阈值判定
        thresholds = risk_view.load_thresholds(self.db, current_user)
        summary = _event_summary(events, thresholds=thresholds, scenario_id=scenario_id)

        # 一次取回该场景「当前账号可见」的数据集列表：既取首个作为代表数据集，也作为
        # 地质工作台的同源兄弟集合。不用 dataset.scenario.datasets —— 那条 relationship
        # 绕过可见性收窄，会把他人 personal 数据集元信息泄漏进 dataset_prior。
        visible_datasets = self.db.scalars(
            select(Dataset)
            .where(
                Dataset.scenario_id == scenario_id,
                Dataset.status == DATASET_STATUS_ACTIVE,
                Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)),
            )
            .order_by(Dataset.id)
        ).all()
        dataset = visible_datasets[0] if visible_datasets else None
        risk_type = events[0].risk_type if events else (DATASET_RISK_TYPES.get(dataset.logical_id) if dataset else None)
        key = _scenario_key(scenario.code, risk_type)

        data: dict[str, Any] = {
            "scenario_id": scenario_id,
            "scenario_code": scenario.code,
            "scenario_key": key,
            "scenario_name": scenario.name,
            "risk_type": risk_type,
            "summary": summary,
            "recent_events": [_recent_event(event, thresholds) for event in events[:20]],
            "scope": {
                "self_only": getattr(current_user, "role", None) == ROLE_SCENARIO_USER,
                "user_id": current_user.id,
            },
            "activity_trend": self._activity_trend(current_user, dataset),
        }

        if key == "network":
            data.update(self._network_workspace(events))
        elif key == "power":
            data.update(self._power_workspace(events))
        elif key == "flight_deck":
            data.update(self._flight_workspace(events))
        elif key == "geological":
            data.update(self._geological_workspace(events, dataset, visible_datasets))
        return ok(data=data)

    def _activity_trend(self, current_user, dataset: Dataset | None) -> list[dict[str, Any]]:
        """近 ACTIVITY_TREND_DAYS 天推理活动趋势（occurred_at = 推理时间，代表使用量）。"""
        days = ACTIVITY_TREND_DAYS
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc)
        stmt = select(InferenceRecord).where(InferenceRecord.executed_at >= start)
        if getattr(current_user, "role", None) == ROLE_SCENARIO_USER:
            stmt = stmt.where(InferenceRecord.user_id == current_user.id)
        elif dataset is not None:
            stmt = stmt.join(ModelVersion, ModelVersion.id == InferenceRecord.model_version_id).where(
                ModelVersion.scenario_id == dataset.scenario_id
            )
        records = self.db.scalars(stmt).all()
        buckets = {
            (today - timedelta(days=offset)).isoformat(): {"total": 0, "risk": 0}
            for offset in range(days - 1, -1, -1)
        }
        for record in records:
            if not record.executed_at:
                continue
            key = record.executed_at.astimezone(timezone.utc).date().isoformat()
            if key in buckets:
                buckets[key]["total"] += 1
                if record.is_risk_event:
                    buckets[key]["risk"] += 1
        return [{"date": day, **buckets[day]} for day in buckets]

    @classmethod
    def _network_workspace(cls, events: list[RiskEvent]) -> dict[str, Any]:
        """网络安全工作台：告警端口、端口偏离度、事件侧包长五段。"""
        port_values = cls._feature_values(events, "L4_DST_PORT") or cls._feature_values(events, "dst_port")
        counts = Counter(port_values)
        total, distinct = len(port_values), len(counts)
        baseline = total / distinct if distinct else 0
        deviation = [
            {
                "value": port,
                "count": count,
                "deviation": round(count / baseline, 2) if baseline else 0,
            }
            for port, count in counts.most_common(10)
        ]
        abnormal = [item for item in deviation if item["deviation"] >= 2]
        return {
            "top_ports": _top(port_values, 8),
            "abnormal_ports": abnormal,
            "port_deviation": deviation,
            "port_baseline": round(baseline, 2),
            "flow_segments": [
                {"label": label, "value": round(sum(cls._feature_nums(events, column)), 2)}
                for label, column in FLOW_BUCKETS
            ],
        }

    @classmethod
    def _power_workspace(cls, events: list[RiskEvent]) -> dict[str, Any]:
        """电力工作台：告警样本电参量、设备×问题类型构成、设备告警排行。"""
        telemetry = []
        for column in POWER_EVENT_PARAMS:
            stats = _stats(cls._feature_nums(events, column))
            telemetry.append(
                {
                    "key": column,
                    "name": POWER_PARAMS.get(column, column),
                    "unit": _POWER_UNITS.get(column, ""),
                    "stats": stats,
                }
            )
        pairs = Counter(
            (
                _clean((event.raw_features or {}).get("Component")) or "未知",
                _clean((event.raw_features or {}).get("IssueType")) or "未知",
            )
            for event in events
            if isinstance(event.raw_features, dict)
        )
        return {
            "telemetry": telemetry,
            "component_issue_distribution": [
                {"component": pair[0], "issue": pair[1], "count": count} for pair, count in pairs.most_common(20)
            ],
            "device_ranking": _top(cls._feature_values(events, "Component"), 10),
            "issue_ranking": _top(cls._feature_values(events, "IssueType"), 10),
        }

    @classmethod
    def _flight_workspace(cls, events: list[RiskEvent]) -> dict[str, Any]:
        """舰面工作台：航向映射坐标散点、最小间距分箱、双机方向角。"""
        positions = [
            {
                "event_id": event.id,
                "x": float(event.fault_position_x) if event.fault_position_x is not None else None,
                "y": float(event.fault_position_y) if event.fault_position_y is not None else None,
                "risk_score": float(event.risk_score) if event.risk_score is not None else None,
                "status": event.status,
            }
            for event in events
        ]
        distances = cls._feature_nums(events, "inter_dist_min")
        bins = ((0, 100), (100, 300), (300, 600), (600, float("inf")))
        labels = ("<100m", "100-300m", "300-600m", "≥600m")
        distribution = []
        for (low, high), label in zip(bins, labels):
            distribution.append(
                {"label": label, "count": sum(1 for value in distances if low <= value < high)}
            )
        return {
            "positions": positions,
            "position_count": sum(1 for item in positions if item["x"] is not None),
            "min_inter_distance": round(min(distances), 2) if distances else None,
            "distance_distribution": distribution,
            "distance_stats": _stats(distances),
            "direction_stats": [
                {"label": name, "stats": _stats(cls._feature_nums(events, name))}
                for name in ("Plane1_dir_mean_deg", "Plane2_dir_mean_deg")
            ],
        }

    @classmethod
    def _geological_workspace(
        cls, events: list[RiskEvent], dataset: Dataset | None, siblings: list[Dataset]
    ) -> dict[str, Any]:
        """地质工作台：因子贡献、触发因素、坡度档位风险排行、静态先验画像。"""
        # 因子贡献：告警样本的因子均值做 0-100 归一
        factor_means: list[dict[str, Any]] = []
        raw_means: dict[str, float] = {}
        for name in GEO_FACTORS:
            stats = _stats(cls._feature_nums(events, name))
            raw_means[name] = (stats or {}).get("mean") or 0
            factor_means.append({"value": name, "mean": raw_means[name]})
        peak = max(raw_means.values()) if raw_means else 0
        contribution = [
            {"value": item["value"], "count": round(item["mean"] / peak * 100, 2) if peak else 0}
            for item in factor_means
        ]

        buckets: dict[str, list[RiskEvent]] = defaultdict(list)
        for event in events:
            features = event.raw_features if isinstance(event.raw_features, dict) else {}
            slope = _num(features.get("Slope"))
            if slope is None:
                continue
            label = "<5°" if slope < 5 else "5-15°" if slope < 15 else "15-25°" if slope < 25 else "≥25°"
            buckets[label].append(event)

        ranking = []
        for label, items in buckets.items():
            scores = [float(item.risk_score or 0) for item in items]
            ranking.append(
                {
                    "label": label,
                    "count": len(items),
                    "mean_risk_score": round(mean(scores), 4) if scores else 0,
                    "max_risk_score": round(max(scores), 4) if scores else 0,
                }
            )
        ranking.sort(key=lambda item: item["mean_risk_score"], reverse=True)

        prior = []
        if dataset is not None:
            reader = _DatasetReader()
            # siblings 由调用方传入，已按 status + visibility 收窄（与代表数据集同口径）；
            # 不要改用 dataset.scenario.datasets，那条 relationship 会绕过可见性过滤。
            # 只保留「标签字段为风险标签」的数据集：dis_global_catalog 的标签是 landslide_size（灾害规模），
            # 若计入会让「先验风险占比」出现恒 100% 的无意义值。
            prior = [
                reader.describe(item)
                for item in sorted(siblings, key=lambda item: item.id)
                if item.logical_id in DATASET_RISK_TYPES
            ]

        return {
            "factor_contribution": contribution,
            "factor_means": factor_means,
            "trigger_distribution": _top(cls._feature_values(events, "landslide_trigger"), 8),
            "slope_ranking": ranking,
            "slope_bucket_count": len(ranking),
            "dataset_prior": prior,
        }

    # ------------------------------------------------------------------
    # 事件特征取值工具
    # ------------------------------------------------------------------
    @staticmethod
    def _feature_values(events: list[RiskEvent], key: str) -> list[str]:
        values = []
        for event in events:
            features = event.raw_features if isinstance(event.raw_features, dict) else {}
            text = _clean(features.get(key))
            if text and text != "?":
                values.append(text)
        return values

    @classmethod
    def _feature_nums(cls, events: list[RiskEvent], key: str) -> list[float]:
        out: list[float] = []
        for text in cls._feature_values(events, key):
            value = _num(text)
            if value is not None:
                out.append(value)
        return out
