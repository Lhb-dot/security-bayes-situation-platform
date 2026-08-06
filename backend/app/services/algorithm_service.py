"""算法 Service（Algorithm）。

对应需求文档章节：6.6（算法接入与训练参数规范）、6.5.2（权限矩阵）。

模型：app.models.algorithm.Algorithm。

关键业务规则（需求 6.6.2 / 6.5.2 权限矩阵）：
1. 算法只能由开发人员通过代码接入系统；管理员不能通过页面新增、修改或删除算法实现。
2. 因此 create / update / delete 一律返回 403（无权限操作）。
3. 查看已注册算法：所有登录用户允许。
4. 算法编码（A2WNB/MAWNB/EMAWNB/DIWNB/PMWNB）为硬编码数据字典（ALGORITHM_CODES），
   仅开发人员可维护，Service 层不做增删改。
"""
from typing import Optional

from sqlalchemy import select

from app.models.algorithm import Algorithm
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.utils.common import get_logger, row_to_dict

logger = get_logger("algorithm")


class AlgorithmService(ServiceBase):
    """算法注册信息查询（只读）。"""

    # ------------------------------------------------------------------
    # 查询（需求 6.5.2：查看已注册算法 → 允许/允许）
    # ------------------------------------------------------------------
    @service_call
    def get_list(self, current_user, only_available: bool = True):
        """算法列表（含 param_schema 参数定义，供训练表单生成）。

        only_available=True 时仅返回 AVAILABLE 算法（默认）。
        """
        self.require_login(current_user)
        stmt = select(Algorithm).order_by(Algorithm.id)
        if only_available:
            stmt = stmt.where(Algorithm.status == "AVAILABLE")
        algorithms = self.db.scalars(stmt).all()
        return ok(data=[row_to_dict(a) for a in algorithms])

    @service_call
    def get(self, current_user, algorithm_id: int):
        """算法详情（含 param_schema，用于动态生成训练参数表单，需求 6.6.3）。"""
        self.require_login(current_user)
        algorithm = self.db.get(Algorithm, algorithm_id)
        if algorithm is None:
            raise ServiceError(404, "算法不存在")
        return ok(data=row_to_dict(algorithm))

    # ------------------------------------------------------------------
    # 增删改（需求 6.6.2：仅开发人员代码接入，管理员禁止）
    # ------------------------------------------------------------------
    @service_call
    def create(self, current_user, **kwargs):
        self.require_admin(current_user)
        raise ServiceError(403, "算法仅支持开发人员通过代码接入，管理员不可新增算法")

    @service_call
    def update(self, current_user, algorithm_id: int, **kwargs):
        self.require_admin(current_user)
        raise ServiceError(403, "算法仅支持开发人员通过代码接入，管理员不可修改算法")

    @service_call
    def delete(self, current_user, algorithm_id: int):
        self.require_admin(current_user)
        raise ServiceError(403, "算法仅支持开发人员通过代码接入，管理员不可删除算法")
