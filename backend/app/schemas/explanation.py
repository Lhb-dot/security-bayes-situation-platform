"""Request model for model-result explanations."""
from typing import Any

from pydantic import BaseModel, Field


class ExplanationStreamRequest(BaseModel):
    scenario: dict[str, Any] = Field(default_factory=dict)
    sample: dict[str, Any] = Field(default_factory=dict)
    model_result: dict[str, Any] = Field(default_factory=dict)
    algorithm_details: dict[str, Any] = Field(default_factory=dict)
    recommended_actions: list[str] = Field(default_factory=list)
    inference_record_id: int | None = Field(None, gt=0)
    model_version_id: int | None = Field(None, gt=0)
