"""场景相关请求模型（/api/v1/scenarios）。

对应 Service：ScenarioService（backend/app/services/scenario_service.py）。
code 必须属于数据字典 SCENARIO_CODES（需求 1.1），Service 层强校验。
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

ScenarioAccessStatus = Literal["ACTUAL", "RESERVED"]


class ScenarioCreate(BaseModel):
    """创建场景（仅管理员；code 走数据字典校验）。"""

    code: str = Field(..., min_length=1, max_length=32, description="场景编码（数据字典）")
    name: str = Field(..., min_length=1, max_length=64, description="场景名称")
    description: Optional[str] = Field(None, description="场景说明")
    access_status: ScenarioAccessStatus = Field("ACTUAL", description="接入状态")


class ScenarioUpdate(BaseModel):
    """更新场景（仅管理员；code 不可修改）。"""

    name: Optional[str] = Field(None, max_length=64, description="场景名称")
    description: Optional[str] = Field(None, description="场景说明")
    access_status: Optional[ScenarioAccessStatus] = Field(None, description="接入状态")
