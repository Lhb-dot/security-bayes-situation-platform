"""推理记录相关请求模型（/api/v1/inference-records）。

对应 Service：InferenceRecordService（backend/app/services/inference_record_service.py）。
"""
from typing import Any, Dict, List, Literal, Optional

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


class InferenceBatchPredict(BaseModel):
    """批量推理请求（页面「批量研判」）。

    - ``source="dataset"``：由服务端按 offset / limit 从模型绑定数据集读样本
    - ``source="samples"``：由调用方直接提交样本列表（CSV 解析后的行）

    两种来源最终都走同一套逐条推理逻辑，行为与单条一致（风险类照常生成
    RiskEvent），保证告警中心与态势统计不断链。
    """

    model_version_id: int = Field(..., gt=0, description="模型版本 ID")
    source: Literal["dataset", "samples"] = Field(
        "dataset", description="样本来源：数据集区间 / 直接提交"
    )
    offset: int = Field(0, ge=0, description="起始行，source=dataset 时生效")
    limit: int = Field(
        50, ge=1, le=200, description="最多研判条数，source=dataset 时生效"
    )
    samples: Optional[List[Dict[str, Any]]] = Field(
        None, description="样本列表，source=samples 时必填"
    )
