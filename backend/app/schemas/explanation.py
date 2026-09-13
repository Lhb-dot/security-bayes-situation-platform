"""Request model for model-result explanations."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExplanationStreamRequest(BaseModel):
    scenario: Dict[str, Any] = Field(default_factory=dict)
    sample: Dict[str, Any] = Field(default_factory=dict)
    model_result: Dict[str, Any] = Field(default_factory=dict)
    algorithm_details: Dict[str, Any] = Field(default_factory=dict)
    recommended_actions: List[str] = Field(default_factory=list)
    inference_record_id: Optional[int] = Field(None, gt=0)
    model_version_id: Optional[int] = Field(None, gt=0)
