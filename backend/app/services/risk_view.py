"""账号级风险视图：同一份事实（risk_score），按**当前账号**的阈值判级。

口径（用户明确要求）：
- 阈值是跟随账号的设置。一个账号在**所有**跟风险有关的地方，都用它自己的阈值
  判断「有没有到高风险」。
- 事实（risk_score）不变，但每个账号看到的是**自己的**风险视图。
- 统计口径同理：不能把别人已经算好的等级直接相加，必须用当前账号的阈值重算。

因此本模块是唯一的判级入口：
- ``RiskEvent.risk_level`` 是**创建者视角**的落库值，只作历史留痕，**不用于对外展示**；
- 任何对外的读取 / 统计，都用 :func:`level_of` 从 ``risk_score`` 重算。

兜底：账号在某场景没有配置阈值时，用 ``DEFAULT_MEDIUM/HIGH_THRESHOLD``（0.5 / 0.8），
与 ``risk_event_service`` 原有的兜底保持一致。
"""
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import select

from app.models.risk_threshold import RiskThreshold
from app.services.constants import (
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
)

#: (medium, high)，均为 0~1
ThresholdPair = Tuple[float, float]


def classify(risk_score: float, medium: float, high: float) -> str:
    """按阈值判级：``>= high`` → HIGH，``>= medium`` → MEDIUM，否则 LOW。

    边界归属为闭区间下界（等于阈值即算命中该档），与 ``risk_event_service`` 原实现一致。
    """
    score = float(risk_score)
    if score >= float(high):
        return RISK_LEVEL_HIGH
    if score >= float(medium):
        return RISK_LEVEL_MEDIUM
    return RISK_LEVEL_LOW


def load_thresholds(db, user) -> Dict[int, ThresholdPair]:
    """一次查出该账号在**全部场景**的阈值：``{scenario_id: (medium, high)}``。

    只返回已配置的场景；未配置的由 :func:`thresholds_for` 兜底，避免在此处写死默认值
    造成「配置了 0.5/0.8 的账号」与「未配置走兜底的账号」不可区分。
    """
    if user is None or getattr(user, "id", None) is None:
        return {}
    rows = db.scalars(
        select(RiskThreshold).where(RiskThreshold.user_id == user.id)
    ).all()
    return {
        int(row.scenario_id): (float(row.medium_threshold), float(row.high_threshold))
        for row in rows
    }


def thresholds_for(
    thresholds: Dict[int, ThresholdPair], scenario_id: Optional[int]
) -> ThresholdPair:
    """取该账号在某场景的阈值；未配置则用兜底常量。"""
    if scenario_id is not None:
        pair = thresholds.get(int(scenario_id))
        if pair is not None:
            return pair
    return (float(DEFAULT_MEDIUM_THRESHOLD), float(DEFAULT_HIGH_THRESHOLD))


def level_of(event, thresholds: Dict[int, ThresholdPair]) -> str:
    """按当前账号阈值算出该事件的等级。

    ``risk_score`` 缺失时（历史脏数据）退回落库的 ``risk_level``，不再凭空造数。
    """
    score = getattr(event, "risk_score", None)
    stored = getattr(event, "risk_level", None)
    if score is None:
        return stored if stored in (RISK_LEVEL_HIGH, RISK_LEVEL_MEDIUM, RISK_LEVEL_LOW) else RISK_LEVEL_LOW
    medium, high = thresholds_for(thresholds, getattr(event, "scenario_id", None))
    return classify(score, medium, high)


def view_of(event, thresholds: Dict[int, ThresholdPair]) -> dict:
    """把事件序列化成**当前账号视角**的 dict（risk_level 已按本人阈值重算）。"""
    from app.utils.common import row_to_dict

    data = row_to_dict(event)
    data["risk_level"] = level_of(event, thresholds)
    return data


def view_events(events: Iterable, thresholds: Dict[int, ThresholdPair]) -> list:
    """批量序列化为当前账号视角。"""
    return [view_of(e, thresholds) for e in events]


def aggregate(events: Iterable, thresholds: Dict[int, ThresholdPair]) -> dict:
    """按**当前账号**阈值聚合风险等级计数，处置状态计数不受阈值影响。

    这是替代 ``SituationSnapshotService._aggregate`` 的口径：等级计数一律重算，
    状态计数沿用落库值。
    """
    from app.services.constants import (
        RISK_EVENT_STATUS_PENDING,
        RISK_EVENT_STATUS_PROCESSING,
        RISK_EVENT_STATUS_RESOLVED,
    )

    events = list(events)
    levels = [level_of(e, thresholds) for e in events]
    return {
        "total_events": len(events),
        "high_count": sum(1 for lv in levels if lv == RISK_LEVEL_HIGH),
        "medium_count": sum(1 for lv in levels if lv == RISK_LEVEL_MEDIUM),
        "low_count": sum(1 for lv in levels if lv == RISK_LEVEL_LOW),
        "pending_count": sum(1 for e in events if e.status == RISK_EVENT_STATUS_PENDING),
        "processing_count": sum(1 for e in events if e.status == RISK_EVENT_STATUS_PROCESSING),
        "resolved_count": sum(1 for e in events if e.status == RISK_EVENT_STATUS_RESOLVED),
    }
