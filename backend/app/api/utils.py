"""API 层响应工具：把 Service 层返回的 ResponseModel 转为 FastAPI 响应。

Service 层约定（app/services/base.py）：所有方法返回
    ResponseModel(code=0, data=..., message="success")
本模块的 unwrap 负责把该结构映射到 HTTP 语义：
- code == 0  → 直接返回（HTTP 200，响应体即 {code, data, message}）；
- code != 0  → 返回 JSONResponse（HTTP 状态码 = code，响应体保持 {code, data, message} 统一结构）。
"""
from typing import Any

from fastapi.responses import JSONResponse

from app.schemas.common import ResponseModel


def unwrap(resp: ResponseModel) -> Any:
    """把 Service 返回的统一响应转换为 FastAPI 响应对象。"""
    if resp.code != 0:
        return JSONResponse(status_code=resp.code, content=resp.model_dump())
    return resp
