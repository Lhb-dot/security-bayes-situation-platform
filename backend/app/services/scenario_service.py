"""场景 Service（Scenario）。

对应需求文档章节：1（三个/四个场景及使用约束）、6.2（场景管理 P0）、6.5.2（权限矩阵）。

模型：app.models.scenario.Scenario。
需求 1.1：场景编码是固定数据字典（4 个场景），创建时用 SCENARIO_CODES 硬编码校验。
权限要点（需求 6.5.2）：查看场景列表/切换场景所有登录用户允许；增删改仅 ADMIN。
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from app.models.app_user import AppUser
from app.models.dataset import Dataset
from app.models.model_version import ModelVersion
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    ROLE_ADMIN,
    SCENARIO_ACCESS_ACTUAL,
    SCENARIO_ACCESS_STATUSES,
    SCENARIO_CODE_MAX_LEN,
    SCENARIO_CODES,
    SCENARIO_NAME_MAX_LEN,
)
from app.utils.common import (
    get_logger,
    row_to_dict,
    validate_enum,
    validate_length,
)

logger = get_logger("scenario")


class ScenarioService(ServiceBase):
    """场景管理：查看（所有登录用户）/ 维护（仅 ADMIN）。"""

    # ------------------------------------------------------------------
    # 查询（需求 6.5.2：查看场景列表及状态、切换场景 → 允许/允许）
    # ------------------------------------------------------------------
    @service_call
    def get_list(self, current_user: Optional[AppUser]):
        """场景列表，标明接入状态（access_status）。

        需求 V3.0 §1.1.6：普通用户仅看到被分配的场景（账号绑定，通常一个）；
        管理员可见全部场景。普通用户未绑定场景时返回空列表。
        """
        self.require_login(current_user)
        stmt = select(Scenario).order_by(Scenario.id)
        if getattr(current_user, "role", None) != ROLE_ADMIN:
            bound = getattr(current_user, "scenario_id", None)
            if bound is None:
                return ok(data=[])
            stmt = stmt.where(Scenario.id == bound)
        scenarios = self.db.scalars(stmt).all()
        return ok(data=[row_to_dict(s) for s in scenarios])

    @service_call
    def get(self, current_user: Optional[AppUser], scenario_id: int):
        """场景详情。"""
        self.require_login(current_user)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")
        return ok(data=row_to_dict(scenario))

    # ------------------------------------------------------------------
    # 维护（仅 ADMIN）
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user,
        code: str,
        name: str,
        description: Optional[str] = None,
        access_status: str = SCENARIO_ACCESS_ACTUAL,
    ):
        """创建场景（仅 ADMIN）。

        数据字典校验：code 必须属于需求文档定义的场景编码 SCENARIO_CODES，
        防止录入需求之外的编码。
        """
        self.require_admin(current_user)
        err = validate_enum(code, SCENARIO_CODES, "code")
        if err:
            raise ServiceError(400, err)
        err = validate_length(name, "name", SCENARIO_NAME_MAX_LEN)
        if err:
            raise ServiceError(400, err)
        err = validate_enum(access_status, SCENARIO_ACCESS_STATUSES, "access_status")
        if err:
            raise ServiceError(400, err)

        exists = self.db.scalar(select(Scenario).where(Scenario.code == code))
        if exists:
            raise ServiceError(400, f"场景编码已存在: {code}")

        now = datetime.now(timezone.utc)
        scenario = Scenario(
            code=code,
            name=name,
            description=description,
            access_status=access_status,
            created_at=now,
            updated_at=now,
        )
        self.db.add(scenario)
        self.commit()
        return ok(data=row_to_dict(scenario), message="场景创建成功")

    @service_call
    def update(
        self,
        current_user,
        scenario_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        access_status: Optional[str] = None,
    ):
        """更新场景（仅 ADMIN）。code 不可修改（唯一键 + 数据字典约束）。"""
        self.require_admin(current_user)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")
        if name is not None:
            err = validate_length(name, "name", SCENARIO_NAME_MAX_LEN)
            if err:
                raise ServiceError(400, err)
            scenario.name = name
        if description is not None:
            scenario.description = description
        if access_status is not None:
            err = validate_enum(access_status, SCENARIO_ACCESS_STATUSES, "access_status")
            if err:
                raise ServiceError(400, err)
            scenario.access_status = access_status
        scenario.updated_at = datetime.now(timezone.utc)
        self.commit()
        return ok(data=row_to_dict(scenario), message="场景更新成功")

    @service_call
    def delete(self, current_user, scenario_id: int):
        """删除场景（仅 ADMIN）。已关联数据集或模型的场景禁止删除。"""
        self.require_admin(current_user)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")
        dataset_count = self.db.scalar(
            select(func.count()).select_from(Dataset).where(
                Dataset.scenario_id == scenario_id
            )
        )
        model_count = self.db.scalar(
            select(func.count()).select_from(ModelVersion).where(
                ModelVersion.scenario_id == scenario_id
            )
        )
        if dataset_count or model_count:
            raise ServiceError(400, "场景已关联数据集或模型，禁止删除")
        self.db.delete(scenario)
        self.commit()
        return ok(message="场景已删除")
