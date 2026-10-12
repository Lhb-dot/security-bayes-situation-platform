"""集中式数据鉴权（authorization）策略。

本模块是服务层**唯一**的数据可见性判定入口。服务不得再自行书写
``if role == ...`` 的可见性分支，一律调用：

- 列表 / 聚合：``authz.scope_datasets(stmt, user)`` 等，给 SELECT 追加可见性条件；
- 单条读写：``authz.can_view_dataset(user, ds)`` / ``authz.require_view_dataset(...)``；
- 动作能力：``authz.can_train(user)`` / ``can_manage_dataset(user, ds)`` 等。

权限模型（2026-10 定稿）
------------------------
角色
    SUPER_ADMIN     服务提供方：只看平台统计 + 自己的数据，看不到各公司具体数据。
    SCENARIO_ADMIN  场景管理员：本场景内最高权限（用户/数据/模型/阈值），跨场景不可见。
    SCENARIO_USER   场景用户：只看自己 + 平台/公司共享的数据。

数据级别（仅数据集携带；由上传者角色决定，创建后不可变）
    platform  平台提供（SUPER_ADMIN 上传）
    company   公司提供（SCENARIO_ADMIN 上传）
    personal  个人提供（SCENARIO_USER 上传）

可见性矩阵
    ================ ================= ====================== =========================
    资源              SUPER_ADMIN       SCENARIO_ADMIN         SCENARIO_USER
    ================ ================= ====================== =========================
    数据集            仅 platform       本场景全部（含 personal） 本场景 platform+company + 本人 personal
    模型              仅本人训练         本场景（含超管已发布）     本场景已发布/推荐
    推理记录           仅本人             本场景全部               仅本人
    风险事件           仅本人             本场景全部               仅本人
    处置记录           跟随事件           跟随事件                 跟随事件
    报告              仅本人             仅本人                   仅本人
    态势快照           全部（仅统计）      本场景                   无
    用户              仅 SCENARIO_ADMIN  本场景 SCENARIO_USER      无
    ================ ================= ====================== =========================

新增受保护资源 = 在本模块加一个 ``scope_*`` / ``can_view_*``，服务层调用即可。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.models.app_user import AppUser
from app.models.dataset import Dataset
from app.models.inference_record import InferenceRecord
from app.models.model_version import ModelVersion
from app.models.report import Report
from app.models.risk_event import RiskEvent
from app.models.scenario import Scenario
from app.models.situation_snapshot import SituationSnapshot
from app.services.constants import (
    DATASET_VISIBILITY_COMPANY,
    DATASET_VISIBILITY_PERSONAL,
    DATASET_VISIBILITY_PLATFORM,
    MODEL_STATUS_PUBLISHED,
    ROLE_SCENARIO_ADMIN,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
    USER_STATUS_ENABLED,
    USER_VISIBLE_MODEL_STATUSES,
)


def role_of(user: object | None) -> Optional[str]:
    return getattr(user, "role", None)


def user_id_of(user: object | None) -> Optional[int]:
    return getattr(user, "id", None)


def scenario_of(user: object | None) -> Optional[int]:
    return getattr(user, "scenario_id", None)


def is_enabled(user: object | None) -> bool:
    return user is not None and getattr(user, "status", None) == USER_STATUS_ENABLED


def default_dataset_visibility(role: Optional[str]) -> str:
    """上传数据集时的默认数据级别（由上传者角色决定，不可自选）。"""
    if role == ROLE_SCENARIO_ADMIN:
        return DATASET_VISIBILITY_COMPANY
    if role == ROLE_SCENARIO_USER:
        return DATASET_VISIBILITY_PERSONAL
    return DATASET_VISIBILITY_PLATFORM


def is_management(user: object | None) -> bool:
    """是否为「管理侧」受众（SUPER_ADMIN / SCENARIO_ADMIN）。

    仅用于**内容分级**（同一份数据，管理侧看算法内部明细，场景用户看裁剪版），
    与「能不能看到这条数据」是两回事 —— 可见性一律由本模块的 can_view_* 决定。
    """
    return role_of(user) in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)


def _super_admin_ids():
    """超管账号 id 子查询（用于「排除超管未发布模型」判定，避免显式 join）。"""
    return select(AppUser.id).where(AppUser.role == ROLE_SUPER_ADMIN)


class Authz:
    """绑定一个数据库会话的鉴权判定器。"""

    def __init__(self, db: Session):
        self.db = db

    # ==================================================================
    # 场景（元数据访问；场景之间严格隔离）
    # ==================================================================
    def scope_scenarios(self, stmt, user):
        role, mine = role_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return stmt
        if role in (ROLE_SCENARIO_ADMIN, ROLE_SCENARIO_USER):
            if mine is None:
                return stmt.where(false())
            return stmt.where(Scenario.id == mine)
        return stmt.where(false())

    def can_access_scenario(self, user, scenario_id) -> bool:
        if not is_enabled(user):
            return False
        role = role_of(user)
        if role == ROLE_SUPER_ADMIN:
            return True
        if role in (ROLE_SCENARIO_ADMIN, ROLE_SCENARIO_USER):
            return scenario_of(user) == scenario_id
        return False

    def require_scenario_access(self, user, scenario_id) -> None:
        from app.services.base import ServiceError

        if not self.can_access_scenario(user, scenario_id):
            raise ServiceError(403, "无权限操作")

    def can_upload_dataset(self, user, scenario_id) -> bool:
        """能否把数据集上传到指定场景（级别由角色决定，见 default_dataset_visibility）。"""
        return self.can_access_scenario(user, scenario_id)

    # ==================================================================
    # 数据集
    # ==================================================================
    def scope_datasets(self, stmt, user):
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return stmt.where(Dataset.visibility == DATASET_VISIBILITY_PLATFORM)
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return stmt.where(false())
            return stmt.where(Dataset.scenario_id == mine)
        if role == ROLE_SCENARIO_USER:
            if mine is None:
                return stmt.where(false())
            return stmt.where(
                Dataset.scenario_id == mine,
                or_(
                    Dataset.visibility != DATASET_VISIBILITY_PERSONAL,
                    Dataset.uploaded_by == uid,
                ),
            )
        return stmt.where(false())

    def can_view_dataset(self, user, dataset: Dataset) -> bool:
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        visibility = getattr(dataset, "visibility", None) or DATASET_VISIBILITY_PLATFORM
        if role == ROLE_SUPER_ADMIN:
            return visibility == DATASET_VISIBILITY_PLATFORM
        if role == ROLE_SCENARIO_ADMIN:
            return mine is not None and dataset.scenario_id == mine
        if role == ROLE_SCENARIO_USER:
            if mine is None or dataset.scenario_id != mine:
                return False
            if visibility == DATASET_VISIBILITY_PERSONAL:
                return dataset.uploaded_by == uid
            return True
        return False

    def require_view_dataset(self, user, dataset: Dataset) -> None:
        from app.services.base import ServiceError

        if not self.can_view_dataset(user, dataset):
            raise ServiceError(403, "无权限操作")

    def can_manage_dataset(self, user, dataset: Dataset) -> bool:
        """数据集管理动作（迭代/追加/停用/删除）。"""
        role, mine = role_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return self.can_view_dataset(user, dataset)
        if role == ROLE_SCENARIO_ADMIN:
            return mine is not None and dataset.scenario_id == mine
        return False

    # ==================================================================
    # 模型版本
    # ==================================================================
    def scope_models(self, stmt, user):
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return stmt.where(ModelVersion.trained_by == uid)
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return stmt.where(false())
            return stmt.where(
                ModelVersion.scenario_id == mine,
                or_(
                    ModelVersion.trained_by.not_in(_super_admin_ids()),
                    ModelVersion.status == MODEL_STATUS_PUBLISHED,
                ),
            )
        if role == ROLE_SCENARIO_USER:
            if mine is None:
                return stmt.where(false())
            return stmt.where(
                ModelVersion.scenario_id == mine,
                ModelVersion.status.in_(USER_VISIBLE_MODEL_STATUSES),
            )
        return stmt.where(false())

    def can_view_model(self, user, model: ModelVersion) -> bool:
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return model.trained_by == uid
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None or model.scenario_id != mine:
                return False
            trainer = self.db.get(AppUser, model.trained_by)
            if (
                trainer is not None
                and trainer.role == ROLE_SUPER_ADMIN
                and model.status != MODEL_STATUS_PUBLISHED
            ):
                return False
            return True
        if role == ROLE_SCENARIO_USER:
            return (
                mine is not None
                and model.scenario_id == mine
                and model.status in USER_VISIBLE_MODEL_STATUSES
            )
        return False

    def require_view_model(self, user, model: ModelVersion) -> None:
        from app.services.base import ServiceError

        if not self.can_view_model(user, model):
            raise ServiceError(403, "无权限操作")

    def can_train(self, user) -> bool:
        """训练：SUPER_ADMIN 与 SCENARIO_ADMIN。"""
        return role_of(user) in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)

    def can_manage_model(self, user, model: ModelVersion) -> bool:
        """模型管理动作（发布/下线/启用/禁用/推荐/删除）。"""
        role, mine = role_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return model.trained_by == user_id_of(user)
        if role == ROLE_SCENARIO_ADMIN:
            return mine is not None and model.scenario_id == mine
        return False

    # ==================================================================
    # 推理记录
    # ==================================================================
    def scope_records(self, stmt, user):
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return stmt.where(false())
            return stmt.where(
                InferenceRecord.model_version_id.in_(
                    select(ModelVersion.id).where(ModelVersion.scenario_id == mine)
                )
            )
        if role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_USER):
            return stmt.where(InferenceRecord.user_id == uid)
        return stmt.where(false())

    def can_view_record(self, user, record: InferenceRecord) -> bool:
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return False
            model = self.db.get(ModelVersion, record.model_version_id)
            return model is not None and model.scenario_id == mine
        if role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_USER):
            return record.user_id == uid
        return False

    def require_view_record(self, user, record: InferenceRecord) -> None:
        from app.services.base import ServiceError

        if not self.can_view_record(user, record):
            raise ServiceError(403, "无权限操作")

    # ==================================================================
    # 风险事件 / 处置
    # ==================================================================
    def scope_events(self, stmt, user):
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return stmt.where(false())
            return stmt.where(RiskEvent.scenario_id == mine)
        if role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_USER):
            return stmt.where(RiskEvent.created_by_user_id == uid)
        return stmt.where(false())

    def can_view_event(self, user, event: RiskEvent) -> bool:
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SCENARIO_ADMIN:
            return mine is not None and event.scenario_id == mine
        if role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_USER):
            return event.created_by_user_id == uid
        return False

    def scope_event_stats(self, stmt, user):
        """**统计口径**的事件范围（只用于聚合计数，绝不用于下发明细）。

        与 :meth:`scope_events` 的区别只在 SUPER_ADMIN：
        - 统计：SUPER 看**平台全量**（系统统计信息，需求「系统管理员可以看到统计数据」）；
        - 明细：SUPER 仅本人（不暴露各公司/用户的具体事故）。
        SCENARIO_ADMIN 仍限本场景，SCENARIO_USER 仍限本人。
        """
        role, uid, mine = role_of(user), user_id_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return stmt
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return stmt.where(false())
            return stmt.where(RiskEvent.scenario_id == mine)
        if role == ROLE_SCENARIO_USER:
            return stmt.where(RiskEvent.created_by_user_id == uid)
        return stmt.where(false())

    def require_view_event(self, user, event: RiskEvent) -> None:
        from app.services.base import ServiceError

        if not self.can_view_event(user, event):
            raise ServiceError(403, "无权限操作")

    def can_handle_event(self, user, event: RiskEvent) -> bool:
        """处置（改状态/评论/隐藏）：与可见性同界 —— 能看见就能处置。"""
        return self.can_view_event(user, event)

    # ==================================================================
    # 报告（所有角色相互独立，仅本人可见）
    # ==================================================================
    def scope_reports(self, stmt, user):
        return stmt.where(Report.generated_by == user_id_of(user))

    def can_view_report(self, user, report: Report) -> bool:
        return report.generated_by == user_id_of(user)

    def require_view_report(self, user, report: Report) -> None:
        from app.services.base import ServiceError

        if not self.can_view_report(user, report):
            raise ServiceError(403, "无权限操作")

    # ==================================================================
    # 态势快照（场景级聚合；SCENARIO_USER 不看跨用户聚合）
    # ==================================================================
    def scope_snapshots(self, stmt, user):
        role, mine = role_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return stmt
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return stmt.where(false())
            return stmt.where(SituationSnapshot.scenario_id == mine)
        return stmt.where(false())

    def can_view_scenario_snapshot(self, user) -> bool:
        return role_of(user) in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)

    # ==================================================================
    # 用户管理
    # ==================================================================
    def scope_users(self, stmt, user):
        """SUPER 只列 SCENARIO_ADMIN；SCENARIO_ADMIN 只列本场景 SCENARIO_USER。"""
        role, mine = role_of(user), scenario_of(user)
        if role == ROLE_SUPER_ADMIN:
            return stmt.where(AppUser.role == ROLE_SCENARIO_ADMIN)
        if role == ROLE_SCENARIO_ADMIN:
            if mine is None:
                return stmt.where(false())
            return stmt.where(
                AppUser.role == ROLE_SCENARIO_USER,
                AppUser.scenario_id == mine,
            )
        return stmt.where(false())

    def can_manage_user(self, actor, target: AppUser) -> bool:
        """能否管理目标账号（改密/禁用/删除/改场景）。"""
        role = role_of(actor)
        if role == ROLE_SUPER_ADMIN:
            return getattr(target, "role", None) == ROLE_SCENARIO_ADMIN
        if role == ROLE_SCENARIO_ADMIN:
            return (
                getattr(target, "role", None) == ROLE_SCENARIO_USER
                and getattr(target, "scenario_id", None) == scenario_of(actor)
            )
        return False

    def can_create_user(self, actor, role: str, scenario_id: Optional[int]) -> bool:
        """能否创建指定角色的账号。"""
        actor_role = role_of(actor)
        if actor_role == ROLE_SUPER_ADMIN:
            return role == ROLE_SCENARIO_ADMIN and scenario_id is not None
        if actor_role == ROLE_SCENARIO_ADMIN:
            return role == ROLE_SCENARIO_USER and scenario_id == scenario_of(actor)
        return False
