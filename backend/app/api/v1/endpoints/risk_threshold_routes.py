"""按账号绑定的风险阈值与变更记录路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_bound_scenario
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.risk_threshold import RiskThresholdUpdate
from app.services.risk_threshold_service import RiskThresholdService
from app.services.threshold_audit_log_service import ThresholdAuditLogService

router = APIRouter(prefix="/risk-thresholds", tags=["风险配置"])


@router.get("", response_model=ResponseModel, summary="查询当前账号全部风险阈值")
def list_risk_thresholds(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(RiskThresholdService(db).get_list(current_user=current_user))


@router.get("/audit-logs", response_model=ResponseModel, summary="查询当前账号阈值修改记录")
def list_threshold_audit_logs(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    scenario_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=200),
):
    return unwrap(
        ThresholdAuditLogService(db).get_list(
            current_user=current_user,
            scenario_id=scenario_id,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{scenario_id}",
    response_model=ResponseModel,
    summary="按场景查询风险阈值（登录用户可读）",
)
def get_risk_threshold(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_bound_scenario),
):
    return unwrap(
        RiskThresholdService(db).get_by_scenario(
            current_user=current_user, scenario_id=scenario_id
        )
    )


@router.put(
    "/{scenario_id}",
    response_model=ResponseModel,
    summary="更新当前账号场景风险阈值（实时生效并写审计日志）",
)
def update_risk_threshold(
    scenario_id: int,
    payload: RiskThresholdUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_bound_scenario),
):
    return unwrap(
        RiskThresholdService(db).update(
            current_user=current_user,
            scenario_id=scenario_id,
            medium_threshold=payload.medium_threshold,
            high_threshold=payload.high_threshold,
        )
    )
