"""API 层：统一鉴权依赖 + 路由注册。

提供 FastAPI 依赖注入函数 get_current_user，所有需要登录态的接口通过
Depends(get_current_user) 注入当前用户。

鉴权方式：读取请求头 X-User-Id（前端 axios 拦截器统一注入），按整数 ID 查询
app_user 表。查不到或已禁用返回 401。
"""
from typing import Optional

from fastapi import Header, HTTPException, Request

from app.db import SessionLocal
from app.models.app_user import AppUser


async def get_current_user(
    request: Request,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> AppUser:
    """FastAPI 依赖：从请求头 X-User-Id 加载当前登录用户。

    用法：
        @router.get("/api/xxx")
        def my_handler(current_user = Depends(get_current_user)):
            ...

    未提供 X-User-Id / 用户不存在 / 账号已禁用 → 401。
    """
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=401, detail="未登录，请先登录系统")

    try:
        user_id = int(x_user_id.strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="无效的用户标识")

    db = SessionLocal()
    try:
        user = db.get(AppUser, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        if user.status != "ENABLED":
            raise HTTPException(status_code=401, detail="账号已被禁用，请联系管理员")
        return user
    finally:
        db.close()
