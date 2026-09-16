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
4. **高置信告警** = `risk_score ≥ 0.8`（替代恒成立的「≥0.5」，后者等于告警总数）；
5. **离散区间字段**（ARFF 分箱值，如 `'(174.365-310.525]'`）取区间中点参与数值统计；
6. 地质场景**不存在「区域」字段**，改按真实字段 `Slope` 的坡度档位分组；
7. 用户端**不聚合他人数据**，后端按 `created_by_user_id` 强制过滤。
"""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
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
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_RISK_TYPES,
    DATASET_STATUS_ACTIVE,
    DATASET_VISIBILITY_COMPANY,
    DATASET_VISIBILITY_PERSONAL,
    DATASET_VISIBILITY_PLATFORM,
    dataset_display_name,
    MODEL_STATUS_PUBLISHED,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_MEDIUM,
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

#: 事件状态
EVENT_STATUS_LABELS = {"PENDING": "待处置", "PROCESSING": "处理中", "RESOLVED": "已处置"}

#: 风险分固定分箱（下限由「只在判风险时建事件」决定，恒 ≥0.5）
SCORE_BINS = (("0.5-0.7", 0.5, 0.7), ("0.7-0.9", 0.7, 0.9), ("0.9-1.0", 0.9, 1.01))

#: 高置信告警阈值
HIGH_CONFIDENCE = 0.8

#: 地质地形因子（DIS_raw_data 真实字段）
GEO_FACTORS = ("Slope", "TWI", "Elevation", "Relief", "SPI", "Dis2roads", "Dis2fault", "Dis2river")

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


def _label_is_risk(value: Any) -> bool:
    """标签是否为正类（风险）。数据字典：0/normal/no/false 为负类。"""
    return _clean(value).lower() not in {"", "?", "0", "normal", "no", "false", "none"}


def _risk_score(scores: list[float]) -> int:
    """场景风险分（0-100）：所辖风险事件 risk_score 的均值 ×100，无事件记 0。"""
    return round(mean(scores) * 100) if scores else 0


def _percent(part: int, total: int) -> float:
    return round(part / total, 4) if total else 0.0


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
                risk = sum(count for value, count in counter.items() if _label_is_risk(value))
                return rows, risk

        _, rows = self.rows(dataset)
        return len(rows), sum(1 for value in _raw_values(rows, index) if _label_is_risk(value))

    def describe(self, dataset: Dataset) -> dict[str, Any]:
        total, risk = self.label_stats(dataset)
        return {
            "dataset_id": dataset.id,
            "logical_id": dataset.logical_id,
            "name": dataset_display_name(dataset.logical_id),
            "version": dataset.version,
            "label_field": dataset.label_field,
            # 标签字段是否属于风险标签（dis_global_catalog 的 label 是灾害规模，不是风险标签）
            "is_risk_label": dataset.logical_id in DATASET_RISK_TYPES,
            "record_count": total,
            "risk_count": risk,
            "risk_rate": _percent(risk, total),
        }


def _group_key(dataset: Dataset) -> str:
    """同源去重键：carrier 三份文件归为一组。"""
    return "carrier_shared_source" if dataset.logical_id in CARRIER_LOGICAL_IDS else dataset.logical_id


def _effective_groups(datasets: list[Dataset]) -> dict[str, list[Dataset]]:
    groups: dict[str, list[Dataset]] = defaultdict(list)
    for dataset in datasets:
        groups[_group_key(dataset)].append(dataset)
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
        if event.status == "RESOLVED":
            buckets[key]["resolved"] += 1
        else:
            buckets[key]["pending"] += 1
    return [{"date": day, **buckets[day]} for day in buckets]


def _event_summary(events: list[RiskEvent], days: int = 7) -> dict[str, Any]:
    status = {"PENDING": 0, "PROCESSING": 0, "RESOLVED": 0}
    today = datetime.now(timezone.utc).date()
    for event in events:
        if event.status in status:
            status[event.status] += 1
    scores = [float(event.risk_score or 0) for event in events]
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
        "high_confidence": sum(1 for score in scores if score >= HIGH_CONFIDENCE),
        "avg_risk_score": round(mean(scores), 4) if scores else 0,
        "max_risk_score": round(max(scores), 4) if scores else 0,
        "score_bins": _score_bins(events),
        "status_funnel": [
            {"label": EVENT_STATUS_LABELS[key], "status": key, "count": value} for key, value in status.items()
        ],
        "daily_trend": _daily_trend(events, days),
    }


def _event_feature_values(events: list[RiskEvent], key: str) -> list[str]:
    values = []
    for event in events:
        features = event.raw_features if isinstance(event.raw_features, dict) else {}
        text = _clean(features.get(key))
        if text and text != "?":
            values.append(text)
    return values


def _recent_event(event: RiskEvent) -> dict[str, Any]:
    data = row_to_dict(event)
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
            select(func.count()).select_from(Algorithm).where(Algorithm.status == "AVAILABLE")
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
                    "pending_count": sum(1 for event in scene_events if event.status == "PENDING"),
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
                    "pending_event_count": sum(1 for event in events if event.status == "PENDING"),
                    "user_count": user_count,
                },
                "scenarios": scenario_cards,
                "runtime": {
                    "risk_event_count": len(events),
                    "pending_event_count": sum(1 for event in events if event.status == "PENDING"),
                    "processing_event_count": sum(1 for event in events if event.status == "PROCESSING"),
                    "resolved_event_count": sum(1 for event in events if event.status == "RESOLVED"),
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

        cards: list[dict[str, Any]] = []
        total_datasets = total_samples = total_models = total_events = total_high = total_medium = 0
        all_scores: list[float] = []
        for scenario in scenarios:
            scene_datasets = [item for item in datasets if item.scenario_id == scenario.id]
            samples, risk_samples, dataset_count = _effective_counts(reader, scene_datasets)
            scene_events = [event for event in events if event.scenario_id == scenario.id]
            high_count = sum(1 for event in scene_events if event.risk_level == RISK_LEVEL_HIGH)
            medium_count = sum(1 for event in scene_events if event.risk_level == RISK_LEVEL_MEDIUM)
            published = published_by_scenario.get(scenario.id, 0)
            scores = [float(event.risk_score or 0) for event in scene_events]

            total_datasets += dataset_count
            total_samples += samples
            total_models += published
            total_events += len(scene_events)
            total_high += high_count
            total_medium += medium_count
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
                    "risk_sample_rate": _percent(risk_samples, samples),
                    "published_model_count": published,
                    "event_count": len(scene_events),
                    "high_risk_count": high_count,
                    # 风险分 = 该场景真实风险事件 risk_score 均值 ×100（无事件记 0）
                    "risk_score": _risk_score(scores),
                    "risk_level": "high" if high_count else ("medium" if medium_count else "low"),
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
                    "risk_level": "high" if total_high else ("medium" if total_medium else "low"),
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
            "datasets": [reader.describe(item) for item in datasets],
            "groups": [
                {
                    "group_id": group_key,
                    "datasets": [item.logical_id for item in group],
                    "record_count": reader.label_stats(_representative(group))[0],
                    "deduplicated": len(group) > 1,
                }
                for group_key, group in groups.items()
            ],
        }

        by_logical = {item.logical_id: item for item in datasets}
        if key == "network":
            data.update(self._network_profile(reader, by_logical))
        elif key == "power":
            data.update(self._power_profile(reader, by_logical))
        elif key == "flight_deck":
            data.update(self._flight_profile(reader, by_logical))
        elif key == "geological":
            data.update(self._geological_profile(reader, by_logical))
        return ok(data=data)

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
        }

    @classmethod
    def _power_profile(cls, reader: _DatasetReader, by_logical: dict[str, Dataset]) -> dict[str, Any]:
        """电力系统数据画像：全量监测样本的电参量、设备/系统/问题分布与设备故障率。"""
        item = by_logical.get("powergrid_knowledgebase")
        fields, rows = cls._dataset_columns(reader, item)
        cmap = _field_index(fields)

        params: list[dict[str, Any]] = []
        for column, label in POWER_PARAMS.items():
            index = _resolve_index(cmap, POWER_PARAM_ALIASES.get(column, (column,)))
            stats = _stats(_nums(rows, index))
            params.append({"name": label, "key": column, "unit": _POWER_UNITS.get(column, ""), "stats": stats})

        component_index = cmap.get("Component")
        target_index = cmap.get("Target_Event")
        device_rates = []
        for component, values in _grouped_pairs(rows, component_index, target_index).items():
            positives = sum(1 for value in values if _label_is_risk(value))
            device_rates.append(
                {
                    "value": component,
                    "count": len(values),
                    "risk_count": positives,
                    "risk_rate": _percent(positives, len(values)),
                }
            )

        target_values = _raw_values(rows, target_index)
        fault_count = sum(1 for value in target_values if _label_is_risk(value))
        return {
            "params": params,
            "fault_count": fault_count,
            "fault_rate": _percent(fault_count, len(target_values)),
            "issues": _top(_raw_values(rows, cmap.get("IssueType")), 8),
            "components": _top(_raw_values(rows, component_index), 8),
            "systems": _top(_raw_values(rows, cmap.get("SystemName")), 8),
            "device_fault_rates": sorted(device_rates, key=lambda item: item["risk_rate"], reverse=True),
            "sources": {"dataset": "powergrid_knowledgebase"},
        }

    @classmethod
    def _flight_profile(cls, reader: _DatasetReader, by_logical: dict[str, Dataset]) -> dict[str, Any]:
        """舰面调度数据画像：以去重后的载体数据集为准（同源三份只算一份）。"""
        item = by_logical.get(CARRIER_CANONICAL) or next(iter(by_logical.values()), None)
        fields, rows = cls._dataset_columns(reader, item)
        cmap = _field_index(fields)

        collision_index = cmap.get("Collision")
        distance_index = cmap.get("inter_dist_min")
        collision_values = _raw_values(rows, collision_index)
        collision_count = sum(1 for value in collision_values if _label_is_risk(value))

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
                    paired.append((_label_is_risk(row[collision_index]), value))

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
        }

    @classmethod
    def _geological_profile(cls, reader: _DatasetReader, by_logical: dict[str, Dataset]) -> dict[str, Any]:
        """地质风险数据画像：主集地形因子 + 各数据集标签 + 全球灾害目录分类。"""
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

        return {
            "factors": factors,
            "factor_count": sum(1 for item in factors if item["stats"]),
            "catalog_distribution": catalog_distribution,
            "sources": {
                "factors": "dis_raw_data",
                "catalog": "dis_global_catalog",
                "note": "数据集无「区域」字段，坡度相关口径一律按真实字段 Slope 分档",
            },
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
        summary = _event_summary(events)

        dataset = self.db.scalar(
            select(Dataset)
            .where(
                Dataset.scenario_id == scenario_id,
                Dataset.status == DATASET_STATUS_ACTIVE,
                Dataset.visibility.in_((DATASET_VISIBILITY_PLATFORM, DATASET_VISIBILITY_COMPANY)),
            )
            .order_by(Dataset.id)
        )
        risk_type = events[0].risk_type if events else (DATASET_RISK_TYPES.get(dataset.logical_id) if dataset else None)
        key = _scenario_key(scenario.code, risk_type)

        data: dict[str, Any] = {
            "scenario_id": scenario_id,
            "scenario_code": scenario.code,
            "scenario_key": key,
            "scenario_name": scenario.name,
            "risk_type": risk_type,
            "summary": summary,
            "recent_events": [_recent_event(event) for event in events[:20]],
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
            data.update(self._geological_workspace(events, dataset))
        return ok(data=data)

    def _activity_trend(self, current_user, dataset: Dataset | None) -> list[dict[str, Any]]:
        """近 7 天推理活动趋势（occurred_at = 推理时间，代表使用量）。"""
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today - timedelta(days=6), datetime.min.time(), tzinfo=timezone.utc)
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
            for offset in range(6, -1, -1)
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
    def _geological_workspace(cls, events: list[RiskEvent], dataset: Dataset | None) -> dict[str, Any]:
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
            siblings = (
                [
                    item
                    for item in dataset.scenario.datasets
                    if item.status == DATASET_STATUS_ACTIVE
                ]
                if getattr(dataset, "scenario", None) is not None
                else []
            )
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
        return _event_feature_values(events, key)

    @classmethod
    def _feature_nums(cls, events: list[RiskEvent], key: str) -> list[float]:
        out: list[float] = []
        for text in cls._feature_values(events, key):
            value = _num(text)
            if value is not None:
                out.append(value)
        return out
