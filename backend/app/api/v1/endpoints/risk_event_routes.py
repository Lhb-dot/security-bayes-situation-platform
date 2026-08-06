"""风险事件路由（/api/v1/risk-events）。

对应 Service：RiskEventService（backend/app/services/risk_event_service.py）。
权限（需求 5.2/6.5.2）：查看/处置 → 登录用户（普通用户仅本人事件，后端强制按
created_by_user_id 过滤）；删除 → 禁止（历史事件必须保持可追溯，Service 返回 400）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.risk_event import RiskEventComment, RiskEventHandle
from app.services.risk_event_service import RiskEventService

router = APIRouter(prefix="/risk-events", tags=["风险事件"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="风险事件列表（普通用户仅本人事件；管理员可按场景/状态过滤）",
)
def list_risk_events(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    scenario_id: Optional[int] = Query(None, description="按场景过滤（仅管理员）"),
    status: Optional[str] = Query(
        None, description="按处置状态过滤：PENDING/PROCESSING/RESOLVED"
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        RiskEventService(db).get_list(
            current_user=current_user,
            scenario_id=scenario_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{event_id}", response_model=ResponseModel, summary="风险事件详情（普通用户仅本人事件）"
)
def get_risk_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        RiskEventService(db).get(current_user=current_user, event_id=event_id)
    )


@router.put(
    "/{event_id}/handle",
    response_model=ResponseModel,
    summary="处置风险事件（更新状态并写入处置记录；USER 仅本人事件）",
)
def handle_risk_event(
    event_id: int,
    payload: RiskEventHandle,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        RiskEventService(db).update_status(
            current_user=current_user,
            event_id=event_id,
            new_status=payload.new_status,
            comment=payload.comment,
        )
    )


@router.post(
    "/{event_id}/comment",
    response_model=ResponseModel,
    summary="追加处置说明（不改变状态）",
)
def comment_risk_event(
    event_id: int,
    payload: RiskEventComment,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        RiskEventService(db).add_comment(
            current_user=current_user,
            event_id=event_id,
            comment=payload.comment,
        )
    )


@router.delete(
    "/{event_id}",
    response_model=ResponseModel,
    summary="删除风险事件（禁止：历史事件必须保持可追溯，需求 5.2）",
)
def delete_risk_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        RiskEventService(db).delete(current_user=current_user, event_id=event_id)
    )
