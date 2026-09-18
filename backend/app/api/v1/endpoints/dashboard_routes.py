"""角色化首页聚合接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["首页看板"])


@router.get("/admin/overview", response_model=ResponseModel, summary="平台管理员首页总览")
def admin_overview(db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    return unwrap(DashboardService(db).get_admin_overview(current_user))


@router.get("/scenarios/{scenario_id}/profile", response_model=ResponseModel, summary="场景管理员首页画像")
def scenario_profile(scenario_id: int, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    return unwrap(DashboardService(db).get_profile(current_user, scenario_id))


@router.get("/scenarios/{scenario_id}/workspace", response_model=ResponseModel, summary="场景用户首页工作台")
def scenario_workspace(scenario_id: int, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    return unwrap(DashboardService(db).get_workspace(current_user, scenario_id))
