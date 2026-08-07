"""态势统计路由（需求 6.2 / 6.8）。

- 个人态势统计 → 所有登录用户（仅本人数据）
- 全局态势统计 → 仅 ADMIN（全平台数据）
- 态势快照查询 → 所有登录用户
- 生成态势快照 → 仅 ADMIN
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.situation_snapshot_service import SituationSnapshotService

router = APIRouter(prefix="/api/situation", tags=["态势统计"])


@router.get("/my-stats", summary="个人态势统计")
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取当前用户的态势统计（按本人风险事件聚合）。"""
    return SituationSnapshotService(db).compute_user_stats(current_user)


@router.get("/scene-stats", summary="全局态势统计")
def get_scene_stats(
    scenario_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员获取全局态势统计（全平台数据，可按场景过滤）。"""
    return SituationSnapshotService(db).compute_scene_stats(current_user, scenario_id=scenario_id)


@router.get("/snapshots", summary="态势快照列表")
def list_snapshots(
    scenario_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取态势快照列表（所有登录用户可读；可按场景过滤）。"""
    return SituationSnapshotService(db).get_list(
        current_user, scenario_id=scenario_id, page=page, page_size=page_size
    )


@router.get("/snapshots/{scenario_id}/latest", summary="最新态势快照")
def get_latest_snapshot(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取指定场景的最新态势快照。"""
    return SituationSnapshotService(db).get_latest(current_user, scenario_id)


@router.post("/snapshots/{scenario_id}", summary="生成态势快照")
def create_snapshot(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理员生成场景态势快照并落库。"""
    return SituationSnapshotService(db).create_snapshot(current_user, scenario_id)
