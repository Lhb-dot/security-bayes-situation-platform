"""用户 Service（AppUser，含 Role 角色常量）。

对应需求文档章节：6.2（用户登录 / 角色鉴权 / 普通用户账号管理 P0）、6.5.1（角色定义）、
6.5.2（权限矩阵）、5.2（数据范围隔离：用户被禁用后历史数据保留）。

模型：app.models.app_user.AppUser（role 字段即角色，无独立 Role 表）。
权限要点（需求 6.5.2）：
- 创建/启用/禁用/重置普通用户账号：仅 ADMIN
- 修改本人密码：本人或 ADMIN
- 用户列表：仅 ADMIN；普通用户仅可查本人信息（get_profile / get）
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from app.models.app_user import AppUser
from app.models.scenario import Scenario
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    PASSWORD_MIN_LEN,
    ROLE_ADMIN,
    ROLE_SCENARIO_ADMIN,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    ROLES,
    USER_STATUS_ENABLED,
    USER_STATUSES,
    USERNAME_MAX_LEN,
)
from app.utils.common import (
    get_logger,
    hash_password,
    paginate,
    row_to_dict,
    validate_enum,
    validate_length,
    validate_required,
    verify_password,
)

logger = get_logger("user")


class UserService(ServiceBase):
    """用户账号管理（ADMIN 管理账号 / 用户本人改密与查询）。"""

    def _get(self, user_id: int) -> AppUser:
        user = self.db.get(AppUser, user_id)
        if user is None:
            raise ServiceError(404, "用户不存在")
        return user

    @staticmethod
    def _safe(user: AppUser) -> dict:
        """对外字段：隐藏 password_hash。"""
        return row_to_dict(user, exclude=("password_hash",))

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @service_call
    def get(self, current_user: Optional[AppUser], user_id: int):
        """查看用户详情：SUPER_ADMIN 可查任意；SCENARIO_ADMIN 仅自己场景；其余仅本人。"""
        self.require_login(current_user)
        user = self._get(user_id)
        role = getattr(current_user, "role", None)
        is_mgmt = role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)
        if not is_mgmt and getattr(current_user, "id", None) != user_id:
            raise ServiceError(403, "无权限操作")
        if role == ROLE_SCENARIO_ADMIN and user.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        return ok(data=self._safe(user))

    @service_call
    def get_profile(self, current_user: Optional[AppUser]):
        """查看本人信息。"""
        self.require_login(current_user)
        return ok(data=self._safe(current_user))

    @service_call
    def get_list(
        self,
        current_user: Optional[AppUser],
        page: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
    ):
        """用户列表（管理级角色）。

        SUPER_ADMIN 看全部用户；SCENARIO_ADMIN 只看自己场景的用户；SCENARIO_USER 无列表权限。
        """
        self.require_scenario_admin(current_user)
        stmt = select(AppUser)
        if getattr(current_user, "role", None) == ROLE_SCENARIO_ADMIN:
            stmt = stmt.where(AppUser.scenario_id == getattr(current_user, "scenario_id", None))
        if keyword:
            stmt = stmt.where(AppUser.username.ilike(f"%{keyword}%"))
        stmt = stmt.order_by(AppUser.id)
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [self._safe(u) for u in result["items"]]
        return ok(data=result)

    # ------------------------------------------------------------------
    # 创建 / 修改（权限矩阵 6.5.2：账号管理仅 ADMIN；改密本人或 ADMIN）
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user: Optional[AppUser],
        username: str,
        password: str,
        role: str = ROLE_USER,
        scenario_id: Optional[int] = None,
    ):
        """创建用户账号（管理级角色）。默认状态 ENABLED。

        三级角色创建规则：
        - SUPER_ADMIN（最外层管理员）：可创建 SCENARIO_ADMIN（必须绑定场景）与 SCENARIO_USER
        - SCENARIO_ADMIN（场景管理员）：只能在自己场景内创建 SCENARIO_USER
        - SUPER_ADMIN 角色只能由引导/种子创建，不通过此接口创建
        """
        self.require_scenario_admin(current_user)
        err = validate_required(
            {"username": username, "password": password}, ("username", "password")
        )
        if err:
            raise ServiceError(400, err)
        err = validate_length(username, "username", USERNAME_MAX_LEN)
        if err:
            raise ServiceError(400, err)
        # 需求将"复杂密码策略"列为 P2，第一阶段仅做基本长度校验
        err = validate_length(password, "password", 128, min_len=PASSWORD_MIN_LEN)
        if err:
            raise ServiceError(400, err)
        err = validate_enum(role, ROLES, "role")
        if err:
            raise ServiceError(400, err)

        if role == ROLE_SUPER_ADMIN:
            raise ServiceError(400, "最外层管理员账号由平台引导创建，不可在此创建")
        if role in (ROLE_SCENARIO_ADMIN, ROLE_SCENARIO_USER) and scenario_id is None:
            raise ServiceError(400, "场景管理员/场景用户必须绑定场景")
        if scenario_id is not None and self.db.get(Scenario, scenario_id) is None:
            raise ServiceError(404, "绑定场景不存在")

        creator_role = getattr(current_user, "role", None)
        if creator_role == ROLE_SCENARIO_ADMIN:
            # 场景管理员只能在自己场景内创建场景用户
            if role != ROLE_SCENARIO_USER:
                raise ServiceError(403, "场景管理员只能创建场景用户")
            if getattr(current_user, "scenario_id", None) != scenario_id:
                raise ServiceError(403, "场景管理员只能在自己场景内创建用户")

        exists = self.db.scalar(
            select(AppUser).where(AppUser.username == username)
        )
        if exists:
            raise ServiceError(400, f"用户名已存在: {username}")

        now = datetime.now(timezone.utc)
        user = AppUser(
            username=username,
            password_hash=hash_password(password),
            role=role,
            status=USER_STATUS_ENABLED,
            scenario_id=scenario_id if role != ROLE_SUPER_ADMIN else None,
            created_at=now,
            updated_at=now,
        )
        self.db.add(user)
        self.commit()
        return ok(data=self._safe(user), message="用户创建成功")

    @service_call
    def update_scenario(
        self,
        current_user: Optional[AppUser],
        user_id: int,
        scenario_id: Optional[int],
    ):
        """分配/修改用户绑定场景（管理级角色）。

        SUPER_ADMIN 可改任意场景管理员/场景用户；SCENARIO_ADMIN 只能改自己场景的用户。
        """
        self.require_scenario_admin(current_user)
        user = self._get(user_id)
        if user.role == ROLE_SUPER_ADMIN:
            raise ServiceError(400, "最外层管理员不绑定场景，无需分配")
        if getattr(current_user, "role", None) == ROLE_SCENARIO_ADMIN:
            if user.scenario_id != getattr(current_user, "scenario_id", None):
                raise ServiceError(403, "场景管理员只能管理自己场景的用户")
        if scenario_id is not None:
            scenario = self.db.get(Scenario, scenario_id)
            if scenario is None:
                raise ServiceError(404, "绑定场景不存在")
        user.scenario_id = scenario_id
        user.updated_at = datetime.now(timezone.utc)
        self.commit()
        return ok(data=self._safe(user), message="场景绑定已更新")

    @service_call
    def update_password(
        self,
        current_user: Optional[AppUser],
        user_id: int,
        new_password: str,
        old_password: Optional[str] = None,
    ):
        """修改密码：USER 仅本人；ADMIN 可重置任意用户（需求 6.2）。

        - 本人改密（/me）：必须传 old_password 并校验正确（路由 PasswordChange 场景）；
        - 管理员重置（/reset-password）：不传 old_password，跳过旧密码校验。
        """
        self.require_login(current_user)
        user = self._get(user_id)
        role = getattr(current_user, "role", None)
        is_mgmt = role in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN)
        if not is_mgmt and getattr(current_user, "id", None) != user_id:
            raise ServiceError(403, "无权限操作")
        # 场景管理员只能重置自己场景用户的密码
        if role == ROLE_SCENARIO_ADMIN and user.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        err = validate_length(
            new_password, "new_password", 128, min_len=PASSWORD_MIN_LEN
        )
        if err:
            raise ServiceError(400, err)

        if old_password is not None:
            if not verify_password(old_password, user.password_hash):
                raise ServiceError(400, "旧密码不正确")
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        self.commit()
        return ok(message="密码修改成功")

    @service_call
    def update_status(
        self,
        current_user: Optional[AppUser],
        user_id: int,
        status: str,
    ):
        """启用/禁用账号（管理级角色）。禁用后历史数据保留（需求 5.2）。"""
        self.require_scenario_admin(current_user)
        err = validate_enum(status, USER_STATUSES, "status")
        if err:
            raise ServiceError(400, err)
        user = self._get(user_id)
        if getattr(current_user, "role", None) == ROLE_SCENARIO_ADMIN and user.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "场景管理员只能管理自己场景的用户")
        if user.id == current_user.id and status != USER_STATUS_ENABLED:
            raise ServiceError(400, "不能禁用当前登录账号")
        user.status = status
        user.updated_at = datetime.now(timezone.utc)
        self.commit()
        return ok(data=self._safe(user), message="账号状态已更新")

    @service_call
    def delete(self, current_user: Optional[AppUser], user_id: int):
        """删除用户（管理级角色）。

        说明：需求文档仅要求"禁用"账号，未要求删除；为满足 CRUD 提供此方法。
        用户存在任何关联业务数据（推理/事件/处置/报告/数据集/模型/阈值等）时
        禁止物理删除，提示改用禁用（保证历史数据可追溯，需求 5.2）。
        """
        self.require_scenario_admin(current_user)
        user = self._get(user_id)
        if getattr(current_user, "role", None) == ROLE_SCENARIO_ADMIN and user.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "场景管理员只能管理自己场景的用户")
        if user.id == current_user.id:
            raise ServiceError(400, "不能删除当前登录账号")

        # 引用保护：任一关联数据存在即拒绝删除
        from app.models.dataset import Dataset
        from app.models.handling_record import HandlingRecord
        from app.models.inference_record import InferenceRecord
        from app.models.model_version import ModelVersion
        from app.models.report import Report
        from app.models.risk_event import RiskEvent
        from app.models.risk_threshold import RiskThreshold
        from app.models.threshold_audit_log import ThresholdAuditLog

        referenced = any(
            self.db.scalar(select(func.count()).select_from(model).where(cond)) > 0
            for model, cond in (
                (Dataset, Dataset.uploaded_by == user_id),
                (ModelVersion, ModelVersion.trained_by == user_id),
                (ModelVersion, ModelVersion.published_by == user_id),
                (InferenceRecord, InferenceRecord.user_id == user_id),
                (RiskEvent, RiskEvent.created_by_user_id == user_id),
                (HandlingRecord, HandlingRecord.handler_id == user_id),
                (Report, Report.generated_by == user_id),
                (RiskThreshold, RiskThreshold.updated_by == user_id),
                (ThresholdAuditLog, ThresholdAuditLog.operator_id == user_id),
            )
        )
        if referenced:
            raise ServiceError(400, "用户存在关联业务数据，禁止删除，请改用禁用")

        self.db.delete(user)
        self.commit()
        return ok(message="用户已删除")
