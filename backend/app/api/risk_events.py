"""风险事件路由（需求 5.2 / 5.3 / 6.8）。

- 查看风险事件列表/详情 → 所有登录用户（普通用户仅本人事件）
- 更新处置状态 → 所有登录用户
- 风险事件不允许删除（需求 5.2 访问控制第 4 条）
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.risk_event_service import RiskEventService

router = APIRouter(prefix="/api/risk-events", tags=["风险事件"])


class UpdateStatusRequest(BaseModel):
    new_status: str = Field(..., pattern="^(PENDING|PROCESSING|RESOLVED)$", description="目标状态")
    comment: Optional[str] = Field(default=None, description="处置说明")


class AddCommentRequest(BaseModel):
    comment: str = Field(..., min_length=1, description="处置说明")


@router.get("", summary="风险事件列表")
def list_risk_events(
    scenario_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取风险事件列表（普通用户强制按本人过滤；管理员可按场景/状态过滤）。"""
    return RiskEventService(db).get_list(
        current_user,
        scenario_id=scenario_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/{event_id}", summary="风险事件详情")
def get_risk_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取风险事件详情（普通用户仅本人事件）。"""
    return RiskEventService(db).get(current_user, event_id)


@router.put("/{event_id}/status", summary="更新处置状态")
def update_risk_event_status(
    event_id: int,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """更新风险事件处置状态（PENDING → PROCESSING → RESOLVED），写入处置记录。"""
    return RiskEventService(db).update_status(
        current_user, event_id, new_status=payload.new_status, comment=payload.comment
    )


@router.post("/{event_id}/comment", summary="追加处置说明")
def add_risk_event_comment(
    event_id: int,
    payload: AddCommentRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """给风险事件追加处置说明（不改状态）。"""
    return RiskEventService(db).add_comment(current_user, event_id, payload.comment)
