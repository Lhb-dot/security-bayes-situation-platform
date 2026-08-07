"""认证路由：登录、获取当前用户信息、修改密码。

对应需求文档章节：6.2（用户登录 / 改密）、6.5.1（角色定义）。

鉴权方式：用户名 + 密码 → 验证通过后返回用户 ID（前端存入 localStorage）；
后续请求通过 X-User-Id 请求头携带用户 ID。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import get_current_user
from app.db import SessionLocal, get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.services.user_service import UserService
from app.utils.common import verify_password, row_to_dict

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, description="原密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码（至少6位）")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/login", summary="用户登录")
def login(payload: LoginRequest):
    """用户名+密码登录，验证通过返回用户信息（前端将 user_id 存入 localStorage）。"""
    db = SessionLocal()
    try:
        user = db.scalar(
            select(AppUser).where(AppUser.username == payload.username)
        )
        if user is None:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if user.status != "ENABLED":
            raise HTTPException(status_code=401, detail="该账号已被禁用，请联系管理员")

        return ResponseModel(
            code=0,
            data=UserService._safe(user),
            message="登录成功",
        )
    finally:
        db.close()


@router.get("/me", summary="获取当前用户信息")
def get_me(current_user: AppUser = Depends(get_current_user)):
    """返回当前登录用户的详细信息（用于前端恢复会话）。"""
    return ResponseModel(code=0, data=UserService._safe(current_user))


@router.post("/change-password", summary="修改本人密码")
def change_password(
    payload: ChangePasswordRequest,
    current_user: AppUser = Depends(get_current_user),
):
    """修改当前登录用户的密码（需验证原密码）。"""
    db = SessionLocal()
    try:
        if not verify_password(payload.old_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="原密码不正确")
        if len(payload.new_password) < 6:
            raise HTTPException(status_code=400, detail="新密码长度至少为 6 位")

        svc = UserService(db)
        return svc.update_password(current_user, current_user.id, payload.new_password)
    finally:
        db.close()
