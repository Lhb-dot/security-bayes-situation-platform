"""推理记录路由（/api/v1/inference-records）。

对应 Service：InferenceRecordService（backend/app/services/inference_record_service.py）。
权限（需求 6.8/6.7.3）：执行推理 → 登录用户（仅 PUBLISHED 模型）；
查看记录 → 登录用户（USER 仅本人）；删除 → 仅 ADMIN。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.inference_record import InferencePredict
from app.services.inference_record_service import InferenceRecordService

router = APIRouter(prefix="/inference-records", tags=["推理记录"])


@router.post(
    "/predict",
    response_model=ResponseModel,
    summary="执行单条推理（登录用户；风险类结果自动生成 RiskEvent）",
)
def predict(
    payload: InferencePredict,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """执行推理并落库推理记录；预测为风险类时生成 RiskEvent（需求 5.2/5.3）。

    说明：任务原路径 `/inference-records/{id}/predict` 中的 id 与
    InferenceRecordService.create_inference 的语义（创建新记录，入参为
    model_version_id）不符，故采用无 id 的 POST /predict 形式。

    ⚠️ 联调占位：当前 `prediction_label`/`risk_score` 由客户端传入（Service 负责
    落库与风险判定）。正式版应接入服务端统一预测入口（需求 6.6.2：算法注册提供
    统一预测格式），由服务端根据 model_version_id + input_features 计算预测结果，
    客户端请求体不再携带这两个字段，避免伪造风险事件。
    """
    return unwrap(
        InferenceRecordService(db).create_inference(
            current_user=current_user,
            model_version_id=payload.model_version_id,
            input_features=payload.input_features,
            prediction_label=payload.prediction_label,
            risk_score=payload.risk_score,
        )
    )


@router.get(
    "",
    response_model=ResponseModel,
    summary="推理记录列表（普通用户仅本人；管理员全部）",
)
def list_inference_records(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    model_version_id: Optional[int] = Query(None, description="按模型版本过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        InferenceRecordService(db).get_list(
            current_user=current_user,
            model_version_id=model_version_id,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{record_id}",
    response_model=ResponseModel,
    summary="推理记录详情（普通用户仅本人）",
)
def get_inference_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        InferenceRecordService(db).get(
            current_user=current_user, record_id=record_id
        )
    )


@router.delete(
    "/{record_id}",
    response_model=ResponseModel,
    summary="删除推理记录（仅管理员；已生成风险事件的记录禁止删除）",
)
def delete_inference_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        InferenceRecordService(db).delete(
            current_user=current_user, record_id=record_id
        )
    )
