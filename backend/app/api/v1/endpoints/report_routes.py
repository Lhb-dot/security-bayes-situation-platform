"""报告路由（/api/v1/reports）。

对应 Service：ReportService（backend/app/services/report_service.py）。
权限（需求 6.8.5/6.2 P1）：生成/查看 → 登录用户（普通用户仅本人数据；
管理员可全平台或指定用户）；删除 → 生成者本人或管理员。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.report import ReportCreate, ReportScheduleUpdate
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["报告管理"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="报告列表（普通用户：本人生成或定向给自己的报告；管理员全部）",
)
def list_reports(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    target_user_id: Optional[int] = Query(
        None, description="按目标用户过滤（仅管理员生效）"
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        ReportService(db).get_list(
            current_user=current_user,
            target_user_id=target_user_id,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{report_id}", response_model=ResponseModel, summary="报告详情"
)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).get(current_user=current_user, report_id=report_id)
    )


@router.post(
    "", response_model=ResponseModel, summary="生成态势报告（普通用户仅本人数据）"
)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).create(
            current_user=current_user,
            title=payload.title,
            report_type=payload.report_type,
            content=payload.content,
            target_user_id=payload.target_user_id,
            file_path=payload.file_path,
            scenario_id=payload.scenario_id,
            format=payload.format,
            scheduled=payload.scheduled,
            interval_days=payload.interval_days,
        )
    )


@router.put(
    "/{report_id}/schedule",
    response_model=ResponseModel,
    summary="保存报告定时配置（暂不执行调度）",
)
def update_report_schedule(
    report_id: int,
    payload: ReportScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).update_schedule(
            current_user=current_user,
            report_id=report_id,
            scheduled=payload.scheduled,
            interval_days=payload.interval_days,
        )
    )


@router.delete(
    "/{report_id}",
    response_model=ResponseModel,
    summary="删除报告（生成者本人或管理员）",
)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ReportService(db).delete(current_user=current_user, report_id=report_id)
    )
