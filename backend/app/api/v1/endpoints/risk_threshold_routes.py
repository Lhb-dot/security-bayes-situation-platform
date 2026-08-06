"""风险阈值配置路由（/api/v1/risk-thresholds）。

对应 Service：RiskThresholdService（backend/app/services/risk_threshold_service.py）。
权限（需求 5.4.1/6.5.2）：查询 → 登录用户；修改 → 仅 ADMIN（自动记录审计日志）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.risk_threshold import RiskThresholdUpdate
from app.services.risk_threshold_service import RiskThresholdService

router = APIRouter(prefix="/risk-thresholds", tags=["风险配置"])


@router.get(
    "/{scenario_id}",
    response_model=ResponseModel,
    summary="按场景查询风险阈值（登录用户可读）",
)
def get_risk_threshold(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        RiskThresholdService(db).get_by_scenario(
            current_user=current_user, scenario_id=scenario_id
        )
    )


@router.put(
    "/{scenario_id}",
    response_model=ResponseModel,
    summary="更新场景风险阈值（仅管理员；实时生效并写审计日志）",
)
def update_risk_threshold(
    scenario_id: int,
    payload: RiskThresholdUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        RiskThresholdService(db).update(
            current_user=current_user,
            scenario_id=scenario_id,
            medium_threshold=payload.medium_threshold,
            high_threshold=payload.high_threshold,
        )
    )
