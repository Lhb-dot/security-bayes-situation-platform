"""场景管理路由（需求 1 / 6.2 / 6.5.2）。

- 查看场景列表/详情 → 所有登录用户
- 创建/更新/删除场景 → 仅 ADMIN
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.scenario_service import ScenarioService

router = APIRouter(prefix="/api/scenarios", tags=["场景管理"])


class CreateScenarioRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, description="场景编码（network_security/power_system/geological_risk/flightdeck_operation）")
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = Field(default=None)
    access_status: str = Field(default="ACTUAL", pattern="^(ACTUAL|RESERVED)$")


class UpdateScenarioRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None)
    access_status: Optional[str] = Field(default=None, pattern="^(ACTUAL|RESERVED)$")


@router.get("", summary="场景列表")
def list_scenarios(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取所有场景列表（含接入状态）。"""
    return ScenarioService(db).get_list(current_user)


@router.get("/{scenario_id}", summary="场景详情")
def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取单个场景详情。"""
    return ScenarioService(db).get(current_user, scenario_id)


@router.post("", summary="创建场景")
def create_scenario(
    payload: CreateScenarioRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员创建场景（code 必须是预定义的场景编码之一）。"""
    return ScenarioService(db).create(
        current_user,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        access_status=payload.access_status,
    )


@router.put("/{scenario_id}", summary="更新场景")
def update_scenario(
    scenario_id: int,
    payload: UpdateScenarioRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员更新场景信息（code 不可修改）。"""
    return ScenarioService(db).update(
        current_user,
        scenario_id,
        name=payload.name,
        description=payload.description,
        access_status=payload.access_status,
    )


@router.delete("/{scenario_id}", summary="删除场景")
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员删除场景（已关联数据集或模型的场景禁止删除）。"""
    return ScenarioService(db).delete(current_user, scenario_id)
