"""风险阈值配置路由（需求 5.4.1 / 6.5.2）。

- 查看场景阈值 → 所有登录用户
- 修改场景阈值 → 仅 ADMIN（含审计日志）
- 查看阈值变更日志 → 仅 ADMIN
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.risk_threshold_service import RiskThresholdService
from app.services.threshold_audit_log_service import ThresholdAuditLogService

router = APIRouter(prefix="/api/thresholds", tags=["风险阈值"])


class UpdateThresholdRequest(BaseModel):
    medium_threshold: float = Field(..., ge=0, le=1, description="中风险阈值 [0,1]")
    high_threshold: float = Field(..., ge=0, le=1, description="高风险阈值 [0,1]（必须大于 medium）")


@router.get("/logs/list", summary="阈值变更日志")
def list_threshold_logs(
    scenario_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员查看阈值变更审计日志（可按场景过滤）。"""
    return ThresholdAuditLogService(db).get_list(
        current_user, scenario_id=scenario_id, page=page, page_size=page_size
    )


@router.get("/{scenario_id}", summary="场景阈值配置")
def get_threshold(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """按场景查询风险阈值配置（所有登录用户可读）。"""
    return RiskThresholdService(db).get_by_scenario(current_user, scenario_id)


@router.put("/{scenario_id}", summary="更新场景阈值")
def update_threshold(
    scenario_id: int,
    payload: UpdateThresholdRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员更新场景阈值（修改后立即生效；自动写入审计日志）。"""
    return RiskThresholdService(db).update(
        current_user,
        scenario_id,
        medium_threshold=payload.medium_threshold,
        high_threshold=payload.high_threshold,
    )
