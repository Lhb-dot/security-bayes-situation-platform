"""数据集相关请求模型（/api/v1/datasets）。

对应 Service：DatasetService（backend/app/services/dataset_service.py）。
fields_schema 结构（需求 3.1）：字段列表，每项含 name / type / role(feature|label) / enum_values(可选)。
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    """上传数据集；场景用户只能上传本人场景的 personal 数据。"""

    logical_id: str = Field(..., min_length=1, max_length=64, description="数据集逻辑 ID")
    name: Optional[str] = Field(
        None,
        max_length=128,
        description="数据集展示名（面向用户的中文名）。缺省时由逻辑 ID 映射兜底",
    )
    scenario_id: int = Field(..., gt=0, description="所属场景 ID")
    file_path: str = Field(..., min_length=1, max_length=255, description="文件路径")
    fields_schema: List[Dict[str, Any]] = Field(
        ..., min_length=1, description="字段结构定义（含 label 与至少一个 feature）"
    )
    label_field: str = Field(..., min_length=1, max_length=64, description="标签字段名")


class DatasetUpdate(BaseModel):
    """修改数据集（仅管理员；已被模型引用时自动创建新版本）。"""

    file_path: Optional[str] = Field(None, max_length=255, description="文件路径")
    fields_schema: Optional[List[Dict[str, Any]]] = Field(
        None, description="字段结构定义"
    )
    label_field: Optional[str] = Field(None, max_length=64, description="标签字段名")


class DatasetRevisionRequest(BaseModel):
    """数据集迭代请求（POST /api/v1/datasets/{dataset_id}/revisions）。

    change_type 决定迭代语义与产物（见 app/services/dataset_iteration.py）：
    - schema_change / label_change：破坏结构兼容，必然新建版本；
    - append_rows / update_rows / resample / replace_file：兼容迭代，
      未被模型引用时原地更新（版本号不变），已引用时新建版本冻结旧文件；
    - metadata：仅改名称等元数据，不触碰数据文件（可见性由上传者角色固定，不可改）。
    """

    change_type: str = Field(
        ..., min_length=1, max_length=24, description="迭代类型（见 dataset_iteration）"
    )
    file_path: Optional[str] = Field(
        None, max_length=255, description="文件路径（文件类迭代）"
    )
    fields_schema: Optional[List[Dict[str, Any]]] = Field(
        None, description="字段结构定义（结构类迭代）"
    )
    label_field: Optional[str] = Field(None, max_length=64, description="标签字段名")
    name: Optional[str] = Field(None, max_length=128, description="数据集名称（元数据迭代）")
    summary: Optional[str] = Field(None, max_length=255, description="迭代摘要")


class DatasetAnalysisRequest(BaseModel):
    """数据集 AI 解析请求。

    regenerate=false 且已保存结果仍然有效时直接下发缓存；true 时忽略缓存重新解析。
    """

    regenerate: bool = Field(False, description="是否忽略已保存结果，重新调用 AI 解析")
