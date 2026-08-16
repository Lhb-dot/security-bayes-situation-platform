"""场景管理路由（/api/v1/scenarios）。

对应 Service：ScenarioService（backend/app/services/scenario_service.py）。
权限（需求 6.5.2）：查看场景列表/切换场景 → 登录用户；增删改 → 仅 ADMIN。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.schemas.scenario import ScenarioCreate, ScenarioUpdate
from app.services.scenario_service import ScenarioService

router = APIRouter(prefix="/scenarios", tags=["场景管理"])


@router.get(
    "", response_model=ResponseModel, summary="场景列表（登录用户）"
)
def list_scenarios(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(ScenarioService(db).get_list(current_user=current_user))


@router.get(
    "/{scenario_id}", response_model=ResponseModel, summary="场景详情（登录用户）"
)
def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        ScenarioService(db).get(current_user=current_user, scenario_id=scenario_id)
    )


@router.get(
    "/{scenario_id}/insights",
    response_model=ResponseModel,
    summary="场景差异化辅助计算（V3.0 §8：网络/电力/地质/航母 前端大屏数据）",
)
def get_scenario_insights(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    dataset_id: Optional[int] = Query(None, description="指定数据集；缺省取场景下首个 ACTIVE 数据集"),
    sample_rows: int = Query(500, ge=10, le=2000, description="参与计算的样本行数上限"),
):
    return unwrap(
        ScenarioService(db).get_insights(
            current_user=current_user,
            scenario_id=scenario_id,
            dataset_id=dataset_id,
            sample_rows=sample_rows,
        )
    )


@router.post(
    "", response_model=ResponseModel, summary="创建场景（仅管理员；code 走数据字典校验）"
)
def create_scenario(
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ScenarioService(db).create(
            current_user=current_user,
            code=payload.code,
            name=payload.name,
            description=payload.description,
            access_status=payload.access_status,
        )
    )


@router.put(
    "/{scenario_id}",
    response_model=ResponseModel,
    summary="更新场景（仅管理员；code 不可修改）",
)
def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ScenarioService(db).update(
            current_user=current_user,
            scenario_id=scenario_id,
            name=payload.name,
            description=payload.description,
            access_status=payload.access_status,
        )
    )


@router.delete(
    "/{scenario_id}",
    response_model=ResponseModel,
    summary="删除场景（仅管理员；已关联数据集/模型时禁止删除）",
)
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        ScenarioService(db).delete(current_user=current_user, scenario_id=scenario_id)
    )
