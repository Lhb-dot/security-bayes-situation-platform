"""用户相关请求模型（/api/v1/users）。

对应 Service：UserService（backend/app/services/user_service.py）。
字段约束与 app/services/constants.py 保持一致：
- 角色：ROLES = (ADMIN, USER)
- 账号状态：USER_STATUSES = (ENABLED, DISABLED)
- 密码最小长度：PASSWORD_MIN_LEN = 6（Service 层校验兜底）
"""
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["ADMIN", "USER"]
UserStatus = Literal["ENABLED", "DISABLED"]


class UserCreate(BaseModel):
    """创建用户（仅管理员；默认状态 ENABLED）。"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    role: Role = Field("USER", description="角色")


class PasswordChange(BaseModel):
    """修改本人密码（需验证旧密码）。"""

    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


class UserUpdatePassword(BaseModel):
    """重置用户密码（仅管理员，无需旧密码）。"""

    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


class UserUpdateStatus(BaseModel):
    """启用/禁用账号（仅管理员；禁用后历史数据保留）。"""

    status: UserStatus = Field(..., description="账号状态")
