"""风险阈值配置请求模型（/api/v1/risk-thresholds）。

对应 Service：RiskThresholdService（backend/app/services/risk_threshold_service.py）。
约束：0 <= medium < high <= 1（DB 层 chk_rt_threshold 兜底），最多两位小数。
"""
from pydantic import BaseModel, Field, field_validator


def _max_2_decimals(v: float) -> float:
    if round(v, 2) != v:
        raise ValueError("阈值最多只能有两位小数")
    return v


class RiskThresholdUpdate(BaseModel):
    """更新场景风险阈值（仅管理员；实时生效并写审计日志）。"""

    medium_threshold: float = Field(..., ge=0, le=1, description="中风险阈值 [0,1]")
    high_threshold: float = Field(..., ge=0, le=1, description="高风险阈值 [0,1]，须大于 medium")

    @field_validator("medium_threshold", "high_threshold")
    @classmethod
    def _check_decimals(cls, v: float) -> float:
        return _max_2_decimals(v)