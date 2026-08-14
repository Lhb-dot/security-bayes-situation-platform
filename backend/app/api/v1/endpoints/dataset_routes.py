"""数据集管理路由（/api/v1/datasets）。

对应 Service：DatasetService（backend/app/services/dataset_service.py）。
权限（需求 2.3/6.5.2）：查看列表与字段预览 → 登录用户（普通用户仅见已发布模型相关数据集）；
上传/修改版本/停用/删除 → 仅 ADMIN。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.dataset import DatasetCreate, DatasetUpdate
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["数据集管理"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="数据集列表（登录用户；普通用户仅见已发布模型关联的数据集）",
)
def list_datasets(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    scenario_id: Optional[int] = Query(None, description="按场景过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        DatasetService(db).get_list(
            current_user=current_user,
            scenario_id=scenario_id,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/{dataset_id}",
    response_model=ResponseModel,
    summary="数据集详情（含字段结构；普通用户仅见已发布模型相关数据集）",
)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        DatasetService(db).get(current_user=current_user, dataset_id=dataset_id)
    )


@router.get(
    "/{dataset_id}/fields-schema",
    response_model=ResponseModel,
    summary="字段预览（需求 3.1.4：字段名/类型/角色/样例值，供推理表单生成）",
)
def get_dataset_fields_schema(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        DatasetService(db).get_fields_schema(
            current_user=current_user, dataset_id=dataset_id
        )
    )


@router.get(
    "/{dataset_id}/preview",
    response_model=ResponseModel,
    summary="数据内容预览（需求 2.4：前 N 条数据/分页/标签列标记）",
)
def get_dataset_preview(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=50, description="每页条数（最多 50）"),
):
    return unwrap(
        DatasetService(db).get_preview(
            current_user=current_user,
            dataset_id=dataset_id,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "", response_model=ResponseModel, summary="上传数据集（仅管理员，版本号自动生成）"
)
def create_dataset(
    payload: DatasetCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        DatasetService(db).create(
            current_user=current_user,
            logical_id=payload.logical_id,
            scenario_id=payload.scenario_id,
            file_path=payload.file_path,
            fields_schema=payload.fields_schema,
            label_field=payload.label_field,
        )
    )


@router.put(
    "/{dataset_id}",
    response_model=ResponseModel,
    summary="修改数据集（仅管理员；已被模型引用时自动创建新版本）",
)
def update_dataset(
    dataset_id: int,
    payload: DatasetUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        DatasetService(db).update(
            current_user=current_user,
            dataset_id=dataset_id,
            file_path=payload.file_path,
            fields_schema=payload.fields_schema,
            label_field=payload.label_field,
        )
    )


@router.post(
    "/{dataset_id}/disable",
    response_model=ResponseModel,
    summary="停用数据集（仅管理员；停用后不得用于新训练，历史数据保留）",
)
def disable_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        DatasetService(db).disable(current_user=current_user, dataset_id=dataset_id)
    )


@router.delete(
    "/{dataset_id}",
    response_model=ResponseModel,
    summary="删除数据集（仅管理员；被模型引用时禁止物理删除，只能停用）",
)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        DatasetService(db).delete(current_user=current_user, dataset_id=dataset_id)
    )
