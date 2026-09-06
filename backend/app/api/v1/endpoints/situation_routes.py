"""态势路由（/api/v1/situation）。

对应 Service：SituationSnapshotService（backend/app/services/situation_snapshot_service.py）。
权限：个人/场景态势 → 登录用户；平台总览 → 仅 SUPER_ADMIN；快照生成 → 管理级角色。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.services.situation_snapshot_service import SituationSnapshotService

router = APIRouter(prefix="/situation", tags=["态势"])


@router.get(
    "/scenes/{scenario_id}",
    response_model=ResponseModel,
    summary="场景态势（真实统计 + 近期风险事件）",
)
def get_scene_situation(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        SituationSnapshotService(db).get_scene_situation(current_user, scenario_id)
    )


@router.get(
    "/me",
    response_model=ResponseModel,
    summary="个人态势统计（普通用户仅本人数据）",
)
def get_my_situation(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(SituationSnapshotService(db).compute_user_stats(current_user))


@router.get(
    "/global",
    response_model=ResponseModel,
    summary="平台总览态势统计（仅管理员；仅 platform 派生事件）",
)
def get_global_situation(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    scenario_id: Optional[int] = Query(None, description="按场景过滤"),
):
    return unwrap(
        SituationSnapshotService(db).compute_scene_stats(current_user, scenario_id)
    )


@router.get(
    "/scenes/{scenario_id}/snapshot/latest",
    response_model=ResponseModel,
    summary="最近一次场景态势快照",
)
def get_latest_snapshot(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        SituationSnapshotService(db).get_latest(current_user, scenario_id)
    )


@router.post(
    "/scenes/{scenario_id}/snapshot",
    response_model=ResponseModel,
    summary="生成场景态势快照（管理级角色）",
)
def create_snapshot(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        SituationSnapshotService(db).create_snapshot(current_user, scenario_id)
    )


@router.get(
    "/snapshots",
    response_model=ResponseModel,
    summary="态势快照列表（按场景过滤可选）",
)
def list_snapshots(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    scenario_id: Optional[int] = Query(None, description="按场景过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页条数"),
):
    return unwrap(
        SituationSnapshotService(db).get_list(
            current_user=current_user,
            scenario_id=scenario_id,
            page=page,
            page_size=page_size,
        )
    )
