"""模型级 AI 评价的请求。"""
from typing import Literal

from pydantic import BaseModel


class ModelEvaluationRequest(BaseModel):
    """跳过缓存，重新生成该角色视角的评价。"""

    regenerate: bool = False
    # 管理端可以显式生成面向普通用户的评价；普通用户
    # 只能取自己角色对应的那份。
    audience: Literal["current", "management", "user"] = "current"
