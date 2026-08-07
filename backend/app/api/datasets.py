"""数据集管理路由（需求 2.2 / 2.3 / 6.5.2）。

- 查看数据集列表/详情/字段 → 所有登录用户
- 上传/修改/停用/删除 → 仅 ADMIN
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/api/datasets", tags=["数据集管理"])


class FieldSchemaItem(BaseModel):
    name: str
    type: str
    role: str = "feature"
    enum_values: Optional[List[str]] = None


class CreateDatasetRequest(BaseModel):
    logical_id: str = Field(..., min_length=1, max_length=64, description="数据集逻辑编码")
    scenario_id: int
    file_path: str = Field(..., min_length=1, max_length=255)
    fields_schema: List[FieldSchemaItem] = Field(..., min_length=1)
    label_field: str = Field(..., min_length=1, max_length=64)


class UpdateDatasetRequest(BaseModel):
    file_path: Optional[str] = Field(default=None, max_length=255)
    fields_schema: Optional[List[FieldSchemaItem]] = Field(default=None)
    label_field: Optional[str] = Field(default=None, max_length=64)


@router.get("", summary="数据集列表")
def list_datasets(
    scenario_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取数据集列表（可按场景过滤；普通用户仅看到与已发布模型相关且启用的数据集）。"""
    return DatasetService(db).get_list(current_user, scenario_id=scenario_id, page=page, page_size=page_size)


@router.get("/{dataset_id}", summary="数据集详情")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取数据集详情（含字段结构）。"""
    return DatasetService(db).get(current_user, dataset_id)


@router.get("/{dataset_id}/fields", summary="数据集字段预览")
def get_fields_schema(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取数据集的字段结构（字段名、类型、角色、枚举值域）。"""
    return DatasetService(db).get_fields_schema(current_user, dataset_id)


@router.post("", summary="上传数据集")
def create_dataset(
    payload: CreateDatasetRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员上传数据集（版本号自动递增，需完成字段校验）。"""
    fields = [f.model_dump() for f in payload.fields_schema]
    return DatasetService(db).create(
        current_user,
        logical_id=payload.logical_id,
        scenario_id=payload.scenario_id,
        file_path=payload.file_path,
        fields_schema=fields,
        label_field=payload.label_field,
    )


@router.put("/{dataset_id}", summary="修改数据集")
def update_dataset(
    dataset_id: int,
    payload: UpdateDatasetRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员修改数据集（已被模型引用则自动创建新版本并保留旧版本）。"""
    fields = [f.model_dump() for f in payload.fields_schema] if payload.fields_schema else None
    return DatasetService(db).update(
        current_user,
        dataset_id,
        file_path=payload.file_path,
        fields_schema=fields,
        label_field=payload.label_field,
    )


@router.put("/{dataset_id}/disable", summary="停用数据集")
def disable_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员停用数据集（被模型引用时只能停用不能删除）。"""
    return DatasetService(db).disable(current_user, dataset_id)


@router.delete("/{dataset_id}", summary="删除数据集")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员物理删除数据集（仅未被引用的数据集可删除）。"""
    return DatasetService(db).delete(current_user, dataset_id)
