"""算法管理路由（/api/v1/algorithms）。

对应 Service：AlgorithmService（backend/app/services/algorithm_service.py）。
权限（需求 6.6.2/6.5.2）：查看已注册算法 → 登录用户；
新增/修改/删除算法实现 → 禁止（仅开发人员代码接入，Service 层统一返回 403）。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.schemas.common import ResponseModel
from app.services.algorithm_service import AlgorithmService

router = APIRouter(prefix="/algorithms", tags=["算法管理"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="算法列表（登录用户；含 param_schema 供训练表单生成）",
)
def list_algorithms(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    only_available: bool = Query(
        True, description="仅返回 AVAILABLE 状态的算法"
    ),
):
    return unwrap(
        AlgorithmService(db).get_list(
            current_user=current_user, only_available=only_available
        )
    )


@router.get(
    "/{algorithm_id}",
    response_model=ResponseModel,
    summary="算法详情（登录用户）",
)
def get_algorithm(
    algorithm_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return unwrap(
        AlgorithmService(db).get(current_user=current_user, algorithm_id=algorithm_id)
    )


@router.post(
    "",
    response_model=ResponseModel,
    summary="新增算法（禁止：仅开发人员代码接入，固定返回 403）",
)
def create_algorithm(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(AlgorithmService(db).create(current_user=current_user))


@router.put(
    "/{algorithm_id}",
    response_model=ResponseModel,
    summary="修改算法（禁止：仅开发人员代码接入，固定返回 403）",
)
def update_algorithm(
    algorithm_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        AlgorithmService(db).update(
            current_user=current_user, algorithm_id=algorithm_id
        )
    )


@router.delete(
    "/{algorithm_id}",
    response_model=ResponseModel,
    summary="删除算法（禁止：仅开发人员代码接入，固定返回 403）",
)
def delete_algorithm(
    algorithm_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    return unwrap(
        AlgorithmService(db).delete(
            current_user=current_user, algorithm_id=algorithm_id
        )
    )
