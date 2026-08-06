"""模型版本路由（/api/v1/model-versions）。

对应 Service：ModelVersionService（backend/app/services/model_version_service.py）。
权限（需求 6.7/6.5.2）：训练/发布/下线/默认推荐 → 仅 ADMIN；查看 → 登录用户
（普通用户仅见 PUBLISHED 模型）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.model_version import (
    ModelVersionCompare,
    ModelVersionCompleteTraining,
    ModelVersionCreate,
    ModelVersionFailTraining,
)
from app.services.model_version_service import ModelVersionService

router = APIRouter(prefix="/model-versions", tags=["模型管理"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="模型版本列表（普通用户仅见 PUBLISHED；管理员可按状态过滤）",
)
def list_model_versions(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    scenario_id: Optional[int] = Query(None, description="按场景过滤"),
    dataset_id: Optional[int] = Query(None, description="按数据集过滤"),
    status: Optional[str] = Query(
        None,
        description="按状态过滤（仅管理员生效）：TRAINING/FAILED/DRAFT/PUBLISHED/OFFLINE",
    ),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        ModelVersionService(db).get_list(
            current_user=current_user,
            scenario_id=scenario_id,
            dataset_id=dataset_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/default",
    response_model=ResponseModel,
    summary="获取某场景+数据集的默认推荐模型（需求 6.7.4）",
)
def get_default_model(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    scenario_id: int = Query(..., description="场景 ID"),
    dataset_id: int = Query(..., description="数据集 ID"),
):
    return unwrap(
        ModelVersionService(db).get_default(
            current_user=current_user,
            scenario_id=scenario_id,
            dataset_id=dataset_id,
        )
    )


@router.post(
    "/compare",
    response_model=ResponseModel,
    summary="模型版本对比（P1；普通用户只比较已发布模型）",
)
def compare_model_versions(
    payload: ModelVersionCompare,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ModelVersionService(db).compare(
            current_user=current_user, model_ids=payload.model_ids
        )
    )


@router.post(
    "", response_model=ResponseModel, summary="启动训练（仅管理员，生成 TRAINING 版本）"
)
def create_model_version(
    payload: ModelVersionCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).create(
            current_user=current_user,
            scenario_id=payload.scenario_id,
            dataset_id=payload.dataset_id,
            algorithm_id=payload.algorithm_id,
            training_parameters=payload.training_parameters,
        )
    )


@router.get(
    "/{model_id}", response_model=ResponseModel, summary="模型版本详情（含评估指标）"
)
def get_model_version(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ModelVersionService(db).get(current_user=current_user, model_id=model_id)
    )


@router.post(
    "/{model_id}/complete-training",
    response_model=ResponseModel,
    summary="训练成功回调（仅管理员）：TRAINING → DRAFT",
)
def complete_model_training(
    model_id: int,
    payload: ModelVersionCompleteTraining,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).complete_training(
            current_user=current_user,
            model_id=model_id,
            evaluation_metrics=payload.evaluation_metrics,
        )
    )


@router.post(
    "/{model_id}/fail",
    response_model=ResponseModel,
    summary="训练失败回调（仅管理员）：TRAINING → FAILED",
)
def fail_model_training(
    model_id: int,
    payload: ModelVersionFailTraining,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).fail_training(
            current_user=current_user,
            model_id=model_id,
            error_message=payload.error_message,
        )
    )


@router.post(
    "/{model_id}/publish",
    response_model=ResponseModel,
    summary="发布模型（仅管理员）：DRAFT → PUBLISHED（OFFLINE 可重新发布）",
)
def publish_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).publish(current_user=current_user, model_id=model_id)
    )


@router.post(
    "/{model_id}/offline",
    response_model=ResponseModel,
    summary="下线模型（仅管理员）：PUBLISHED → OFFLINE（自动清除默认推荐状态）",
)
def offline_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).offline(current_user=current_user, model_id=model_id)
    )


@router.post(
    "/{model_id}/set-default",
    response_model=ResponseModel,
    summary="设为默认推荐模型（仅管理员；每个场景+数据集最多一个）",
)
def set_default_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).set_default(current_user=current_user, model_id=model_id)
    )


@router.post(
    "/{model_id}/clear-default",
    response_model=ResponseModel,
    summary="取消默认推荐状态（仅管理员）",
)
def clear_default_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).clear_default(
            current_user=current_user, model_id=model_id
        )
    )


@router.delete(
    "/{model_id}",
    response_model=ResponseModel,
    summary="删除模型版本（仅管理员；被推理/事件引用时禁止删除）",
)
def delete_model_version(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ModelVersionService(db).delete(current_user=current_user, model_id=model_id)
    )
