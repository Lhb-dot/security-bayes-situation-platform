"""推理记录路由（需求 4 / 6.7.3 / 6.8）。

- 查看推理记录列表/详情 → 所有登录用户
- 执行推理 → 所有登录用户
- 删除推理记录 → 仅 ADMIN
"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.inference_record_service import InferenceRecordService

router = APIRouter(prefix="/api/inference", tags=["推理记录"])


class CreateInferenceRequest(BaseModel):
    model_version_id: int = Field(..., description="模型版本 ID")
    input_features: Dict[str, Any] = Field(..., description="输入特征 JSON 对象")
    prediction_label: str = Field(..., description="模型预测标签")
    risk_score: Optional[float] = Field(default=None, ge=0, le=1, description="风险概率/置信度 [0,1]")
    executed_at: Optional[str] = Field(default=None, description="推理执行时间（ISO 8601）")


@router.get("", summary="推理记录列表")
def list_inference(
    model_version_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取推理记录列表（普通用户仅见本人；管理员可看全部并按模型版本过滤）。"""
    return InferenceRecordService(db).get_list(
        current_user, model_version_id=model_version_id, page=page, page_size=page_size
    )


@router.get("/{record_id}", summary="推理记录详情")
def get_inference(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取单条推理记录详情。"""
    return InferenceRecordService(db).get(current_user, record_id)


@router.post("", summary="执行推理")
def create_inference(
    payload: CreateInferenceRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """执行单条样本推理并落库（预测为风险类时自动生成 RiskEvent）。

    prediction_label 和 risk_score 由上层算法模块返回后传入 Service 层。
    """
    executed_at = None
    if payload.executed_at:
        try:
            executed_at = datetime.fromisoformat(payload.executed_at)
        except ValueError:
            pass

    return InferenceRecordService(db).create_inference(
        current_user,
        model_version_id=payload.model_version_id,
        input_features=payload.input_features,
        prediction_label=payload.prediction_label,
        risk_score=payload.risk_score,
        executed_at=executed_at,
    )


@router.delete("/{record_id}", summary="删除推理记录")
def delete_inference(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员删除推理记录（已生成风险事件的禁止删除）。"""
    return InferenceRecordService(db).delete(current_user, record_id)
