"""API 层依赖注入：当前用户解析与管理员校验。

对应需求文档章节：6.2（用户登录 / 角色鉴权 P0）、6.5.2（权限矩阵）。

说明：
- 项目尚未实现正式登录（JWT/会话），本模块先以请求头 `X-User-Id` 透传当前用户 ID，
  便于联调与开发；接入正式登录后，仅需替换 get_current_user 内部实现
  （从令牌解析用户），路由层无需改动。
- 所有权限校验在后端执行（需求 6.5.2：前端隐藏按钮不能替代权限控制）。
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.app_user import AppUser
from app.services.constants import ROLE_ADMIN, USER_STATUS_ENABLED


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(
        None,
        alias="X-User-Id",
        description="当前登录用户 ID（开发阶段透传；正式接入登录后替换为令牌解析）",
    ),
) -> AppUser:
    """解析当前登录用户（未提供 / 未登录 / 账号被禁用 → 401）。"""
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="未登录或账号不可用")
    user = db.get(AppUser, x_user_id)
    if user is None or user.status != USER_STATUS_ENABLED:
        raise HTTPException(status_code=401, detail="未登录或账号不可用")
    return user


def require_admin(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    """管理员专用接口依赖：非 ADMIN → 403。"""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="无权限操作")
    return current_user
