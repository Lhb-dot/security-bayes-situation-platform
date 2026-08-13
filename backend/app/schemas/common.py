"""统一 API 响应模型（Service 层通用返回格式）。

对应任务约定：所有 Service 函数统一返回
    {"code": 0, "data": ..., "message": "success"}
- code == 0 表示成功
- code == 400 表示业务/参数校验失败
- code == 403 表示权限不足（"无权限操作"）
- code == 404 表示资源不存在
- code == 500 表示数据库或未预期异常

使用示例：
    from app.schemas.common import ok, fail
    return ok(data=user_dict)                # {"code": 0, "data": ..., "message": "success"}
    return fail(code=400, message="缺少必填字段: username")
"""
from typing import Any

from pydantic import BaseModel


class ResponseModel(BaseModel):
    """统一响应结构：code / data / message。"""

    code: int = 0
    data: Any = None
    message: str = "success"


def ok(data: Any = None, message: str = "success", code: int = 0) -> ResponseModel:
    """成功响应（默认 code=0）。"""
    return ResponseModel(code=code, data=data, message=message)


def fail(code: int = 400, message: str = "请求失败") -> ResponseModel:
    """失败响应（data 恒为 None）。"""
    return ResponseModel(code=code, data=None, message=message)
