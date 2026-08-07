"""用户管理路由（需求 6.2 / 6.5.2）。

- 用户列表/创建/启用禁用/删除 → 仅 ADMIN
- 查看用户详情 → 本人或 ADMIN
- 修改密码 → 本人或 ADMIN
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["用户管理"])


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="USER", pattern="^(ADMIN|USER)$")


class UpdatePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(ENABLED|DISABLED)$")


@router.get("", summary="用户列表")
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    keyword: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员查看所有用户列表（支持按用户名搜索）。"""
    return UserService(db).get_list(current_user, page=page, page_size=page_size, keyword=keyword)


@router.get("/{user_id}", summary="用户详情")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """查看用户详情（本人或 ADMIN）。"""
    return UserService(db).get(current_user, user_id)


@router.post("", summary="创建用户")
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员创建用户账号（默认角色 USER）。"""
    return UserService(db).create(current_user, username=payload.username, password=payload.password, role=payload.role)


@router.put("/{user_id}/password", summary="修改密码")
def update_password(
    user_id: int,
    payload: UpdatePasswordRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """修改用户密码（本人或 ADMIN）。"""
    return UserService(db).update_password(current_user, user_id, payload.new_password)


@router.put("/{user_id}/status", summary="启用/禁用账号")
def update_status(
    user_id: int,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员启用或禁用用户账号。"""
    return UserService(db).update_status(current_user, user_id, payload.status)


@router.delete("/{user_id}", summary="删除用户")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员删除用户（有关联业务数据时禁止删除，建议改用禁用）。"""
    return UserService(db).delete(current_user, user_id)
