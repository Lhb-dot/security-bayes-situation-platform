"""模型版本路由（需求 6.7 / 6.5.2）。

- 查看模型列表/详情/默认推荐/对比 → 所有登录用户
- 训练/发布/下线/设默认/删除 → 仅 ADMIN
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.model_version_service import ModelVersionService

router = APIRouter(prefix="/api/models", tags=["模型管理"])


class CreateModelRequest(BaseModel):
    scenario_id: int
    dataset_id: int
    algorithm_id: int
    training_parameters: Dict = Field(default_factory=dict, description="训练参数 JSON 对象")


class CompleteTrainingRequest(BaseModel):
    evaluation_metrics: Dict = Field(..., description="评估指标 JSON 对象")


class FailTrainingRequest(BaseModel):
    error_message: Optional[str] = Field(default=None)


class CompareRequest(BaseModel):
    model_ids: List[int] = Field(..., min_length=1)


@router.get("", summary="模型版本列表")
def list_models(
    scenario_id: Optional[int] = Query(default=None),
    dataset_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None, description="模型状态过滤（仅 ADMIN 可用）"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取模型版本列表（普通用户仅见已发布；管理员可按状态过滤）。"""
    return ModelVersionService(db).get_list(
        current_user,
        scenario_id=scenario_id,
        dataset_id=dataset_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/default", summary="默认推荐模型")
def get_default_model(
    scenario_id: int = Query(..., description="场景 ID"),
    dataset_id: int = Query(..., description="数据集 ID"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取某"场景＋数据集"的默认推荐模型（无默认返回 null）。"""
    return ModelVersionService(db).get_default(current_user, scenario_id, dataset_id)


@router.get("/{model_id}", summary="模型版本详情")
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取模型版本详情（含评估指标）。"""
    return ModelVersionService(db).get(current_user, model_id)


@router.post("", summary="启动训练")
def create_model(
    payload: CreateModelRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员启动训练（生成 TRAINING 状态模型版本，校验数据集属于所选场景）。"""
    return ModelVersionService(db).create(
        current_user,
        scenario_id=payload.scenario_id,
        dataset_id=payload.dataset_id,
        algorithm_id=payload.algorithm_id,
        training_parameters=payload.training_parameters,
    )


@router.post("/{model_id}/complete", summary="训练完成")
def complete_training(
    model_id: int,
    payload: CompleteTrainingRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """标记训练成功：TRAINING → DRAFT，保存评估指标。"""
    return ModelVersionService(db).complete_training(current_user, model_id, payload.evaluation_metrics)


@router.post("/{model_id}/fail", summary="训练失败")
def fail_training(
    model_id: int,
    payload: FailTrainingRequest = FailTrainingRequest(),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """标记训练失败：TRAINING → FAILED。"""
    return ModelVersionService(db).fail_training(current_user, model_id, payload.error_message)


@router.post("/{model_id}/publish", summary="发布模型")
def publish_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员发布模型：DRAFT → PUBLISHED 或 OFFLINE → PUBLISHED（重新发布）。"""
    return ModelVersionService(db).publish(current_user, model_id)


@router.post("/{model_id}/offline", summary="下线模型")
def offline_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员下线模型：PUBLISHED → OFFLINE（默认模型自动取消默认状态）。"""
    return ModelVersionService(db).offline(current_user, model_id)


@router.post("/{model_id}/set-default", summary="设为默认推荐")
def set_default_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员设置默认推荐模型（每个"场景+数据集"最多一个默认；必须已发布）。"""
    return ModelVersionService(db).set_default(current_user, model_id)


@router.post("/compare", summary="模型版本对比")
def compare_models(
    payload: CompareRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """对比多个模型版本的评估指标（普通用户只能比较已发布模型）。"""
    return ModelVersionService(db).compare(current_user, payload.model_ids)


@router.delete("/{model_id}", summary="删除模型")
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员删除模型版本（被推理记录或风险事件引用的禁止删除）。"""
    return ModelVersionService(db).delete(current_user, model_id)
