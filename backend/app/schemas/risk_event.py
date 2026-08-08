"""风险事件相关请求模型（/api/v1/risk-events）。

对应 Service：RiskEventService（backend/app/services/risk_event_service.py）。
处置状态机：PENDING → PROCESSING / RESOLVED；PROCESSING → RESOLVED（Service 强制校验）。
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskEventStatus = Literal["PENDING", "PROCESSING", "RESOLVED"]


class RiskEventHandle(BaseModel):
    """处置风险事件（更新状态并写入处置记录）。"""

    new_status: RiskEventStatus = Field(..., description="目标处置状态")
    comment: Optional[str] = Field(None, description="处置说明")


class RiskEventComment(BaseModel):
    """追加处置说明（不改变状态）。"""

    comment: str = Field(..., min_length=1, description="处置说明")
