"""模型版本相关请求模型（/api/v1/model-versions）。

对应 Service：ModelVersionService（backend/app/services/model_version_service.py）。
状态机由 Service 按 MODEL_STATUS_TRANSITIONS 强制校验，此处不做枚举约束。
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelVersionCreate(BaseModel):
    """启动训练（仅管理员；生成 TRAINING 状态版本）。"""

    scenario_id: int = Field(..., gt=0, description="场景 ID")
    dataset_id: int = Field(..., gt=0, description="数据集 ID")
    algorithm_id: int = Field(..., gt=0, description="算法 ID")
    training_parameters: Dict[str, Any] = Field(
        ..., description="训练参数（按算法 param_schema 校验）"
    )


class ModelVersionCompare(BaseModel):
    """模型版本对比（P1；普通用户只比较已发布模型）。"""

    model_ids: List[int] = Field(..., min_length=1, description="待对比的模型版本 ID 列表")


class ModelVersionCompleteTraining(BaseModel):
    """训练成功回调（仅管理员）：TRAINING → DRAFT。"""

    evaluation_metrics: Dict[str, Any] = Field(..., description="评估指标")


class ModelVersionFailTraining(BaseModel):
    """训练失败回调（仅管理员）：TRAINING → FAILED。"""

    error_message: Optional[str] = Field(None, description="失败原因")
