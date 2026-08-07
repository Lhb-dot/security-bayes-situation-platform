"""报告路由（需求 6.2 / 6.8.5）。

- 查看报告列表/详情 → 所有登录用户（普通用户仅本人相关）
- 生成报告 → 所有登录用户
- 删除报告 → 生成者本人或 ADMIN
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["报告管理"])


class CreateReportRequest(BaseModel):
    report_type: str = Field(..., pattern="^(SCENE_SNAPSHOT|USER_SNAPSHOT)$", description="报告类型")
    content: str = Field(..., min_length=1, description="报告内容")
    target_user_id: Optional[int] = Field(default=None, description="目标用户（普通用户只能为本人）")
    file_path: Optional[str] = Field(default=None)


@router.get("", summary="报告列表")
def list_reports(
    target_user_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取报告列表（普通用户仅本人相关；管理员可按目标用户过滤）。"""
    return ReportService(db).get_list(
        current_user, target_user_id=target_user_id, page=page, page_size=page_size
    )


@router.get("/{report_id}", summary="报告详情")
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取报告详情。"""
    return ReportService(db).get(current_user, report_id)


@router.post("", summary="生成报告")
def create_report(
    payload: CreateReportRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """生成态势报告（普通用户只能基于本人数据；管理员可生成全平台或指定用户报告）。"""
    return ReportService(db).create(
        current_user,
        report_type=payload.report_type,
        content=payload.content,
        target_user_id=payload.target_user_id,
        file_path=payload.file_path,
    )


@router.delete("/{report_id}", summary="删除报告")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """删除报告（生成者本人或管理员）。"""
    return ReportService(db).delete(current_user, report_id)
