"""用户 AI 配置的请求体。"""
from typing import Optional

from pydantic import BaseModel, Field


class AISettingUpdate(BaseModel):
    provider: str = Field("openai-compatible", min_length=1, max_length=32)
    base_url: str = Field(..., min_length=1, max_length=255)
    model: str = Field(..., min_length=1, max_length=128)
    api_key: Optional[str] = Field(None, min_length=1, max_length=4096)
    enabled: bool = True
