"""处置记录路由（需求 4 / 5.2 / 6.5.2）。

- 查看处置记录列表/详情 → 所有登录用户（普通用户仅本人相关）
- 创建处置记录 → 所有登录用户
- 删除处置记录 → 仅 ADMIN
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.handling_record_service import HandlingRecordService

router = APIRouter(prefix="/api/handling-records", tags=["处置记录"])


class CreateHandlingRecordRequest(BaseModel):
    risk_event_id: int = Field(..., description="风险事件 ID")
    action: str = Field(..., pattern="^(ASSIGN|UPDATE_STATUS|ADD_COMMENT)$")
    comment: Optional[str] = Field(default=None)
    status_before: Optional[str] = Field(default=None)
    status_after: Optional[str] = Field(default=None)


@router.get("", summary="处置记录列表")
def list_handling_records(
    risk_event_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取处置记录列表（普通用户仅本人相关；可按风险事件过滤）。"""
    return HandlingRecordService(db).get_list(
        current_user, risk_event_id=risk_event_id, page=page, page_size=page_size
    )


@router.get("/{record_id}", summary="处置记录详情")
def get_handling_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取处置记录详情。"""
    return HandlingRecordService(db).get(current_user, record_id)


@router.post("", summary="创建处置记录")
def create_handling_record(
    payload: CreateHandlingRecordRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """登记处置操作（USER 仅本人事件；ADMIN 全部）。

    action=UPDATE_STATUS 时校验状态流转合法性并同步更新事件状态。
    """
    return HandlingRecordService(db).create(
        current_user,
        risk_event_id=payload.risk_event_id,
        action=payload.action,
        comment=payload.comment,
        status_before=payload.status_before,
        status_after=payload.status_after,
    )


@router.delete("/{record_id}", summary="删除处置记录")
def delete_handling_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员删除处置记录。"""
    return HandlingRecordService(db).delete(current_user, record_id)
