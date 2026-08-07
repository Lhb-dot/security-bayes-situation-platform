"""算法注册路由（需求 6.6 / 6.5.2）。

算法由开发人员通过代码接入系统，管理员不可通过页面新增/修改/删除算法。
路由仅提供只读查询（所有登录用户可查看）。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import get_current_user
from app.db import get_db
from app.models.app_user import AppUser
from app.services.algorithm_service import AlgorithmService

router = APIRouter(prefix="/api/algorithms", tags=["算法管理"])


@router.get("", summary="算法列表")
def list_algorithms(
    only_available: bool = Query(default=True, description="仅返回可用算法"),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取已注册算法列表（含 param_schema 参数定义，供训练表单动态生成）。"""
    return AlgorithmService(db).get_list(current_user, only_available=only_available)


@router.get("/{algorithm_id}", summary="算法详情")
def get_algorithm(
    algorithm_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """获取算法详情（含完整 param_schema，用于动态生成训练参数表单）。"""
    return AlgorithmService(db).get(current_user, algorithm_id)
