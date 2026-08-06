"""用户管理路由（/api/v1/users）。

对应 Service：UserService（backend/app/services/user_service.py）。
权限（需求 6.5.2）：账号管理仅 ADMIN；修改本人密码本人或 ADMIN；用户列表仅 ADMIN。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.user import (
    PasswordChange,
    UserCreate,
    UserUpdatePassword,
    UserUpdateStatus,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="用户列表（仅管理员，支持分页与用户名模糊搜索）",
)
def list_users(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
    keyword: Optional[str] = Query(None, description="用户名模糊搜索"),
):
    return unwrap(
        UserService(db).get_list(
            current_user=current_user, page=page, page_size=page_size, keyword=keyword
        )
    )


@router.get(
    "/me", response_model=ResponseModel, summary="查看本人信息（登录用户）"
)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(UserService(db).get_profile(current_user=current_user))


@router.get(
    "/{user_id}",
    response_model=ResponseModel,
    summary="查看用户详情（ADMIN 任意用户；USER 仅本人）",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(UserService(db).get(current_user=current_user, user_id=user_id))


@router.post(
    "", response_model=ResponseModel, summary="创建用户（仅管理员）"
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        UserService(db).create(
            current_user=current_user,
            username=payload.username,
            password=payload.password,
            role=payload.role,
        )
    )


@router.put(
    "/{user_id}/password",
    response_model=ResponseModel,
    summary="修改本人密码（需验证旧密码；ADMIN 重置他人请用 /reset-password）",
)
def update_user_password(
    user_id: int,
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        UserService(db).update_password(
            current_user=current_user,
            user_id=user_id,
            new_password=payload.new_password,
            old_password=payload.old_password,
        )
    )


@router.put(
    "/{user_id}/reset-password",
    response_model=ResponseModel,
    summary="重置用户密码（仅管理员；无需旧密码）",
)
def reset_user_password(
    user_id: int,
    payload: UserUpdatePassword,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        UserService(db).update_password(
            current_user=current_user,
            user_id=user_id,
            new_password=payload.new_password,
        )
    )


@router.put(
    "/{user_id}/status",
    response_model=ResponseModel,
    summary="启用/禁用账号（仅管理员；禁用后历史数据保留）",
)
def update_user_status(
    user_id: int,
    payload: UserUpdateStatus,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        UserService(db).update_status(
            current_user=current_user, user_id=user_id, status=payload.status
        )
    )


@router.delete(
    "/{user_id}",
    response_model=ResponseModel,
    summary="删除用户（仅管理员；存在关联业务数据时禁止删除，请改用禁用）",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(UserService(db).delete(current_user=current_user, user_id=user_id))
