"""推理记录相关请求模型（/api/v1/inference-records）。

对应 Service：InferenceRecordService（backend/app/services/inference_record_service.py）。
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class InferencePredict(BaseModel):
    """执行单条推理（登录用户；仅 PUBLISHED 模型可推理）。

    说明：prediction_label / risk_score 当前由客户端传入（联调占位，见路由文件注释），
    正式版应由服务端统一预测入口计算，避免客户端伪造风险事件。
    """

    model_version_id: int = Field(..., gt=0, description="模型版本 ID")
    input_features: Dict[str, Any] = Field(
        ..., description="输入特征（按数据集字段结构校验）"
    )
    prediction_label: str = Field(..., min_length=1, description="预测标签")
    risk_score: Optional[float] = Field(
        None, ge=0, le=1, description="风险类概率/置信度 [0,1]"
    )
