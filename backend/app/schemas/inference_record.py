"""推理记录相关请求模型（/api/v1/inference-records）。

对应 Service：InferenceRecordService（backend/app/services/inference_record_service.py）。
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class InferencePredict(BaseModel):
    """执行单条推理（登录用户；仅 PUBLISHED 模型可推理）。

    预测结果（prediction_label / risk_score）由服务端统一预测入口根据
    model_version_id + input_features 计算，客户端不再提交这两个字段（需求 6.6.2）。
    """

    model_version_id: int = Field(..., gt=0, description="模型版本 ID")
    input_features: Dict[str, Any] = Field(
        ..., description="输入特征（按数据集字段结构校验）"
    )
