"""处置记录 Service（HandlingRecord）。

对应需求文档章节：4（风险结果统一为 RiskEvent 后跟进处置）、5.2（处置状态流转）、
6.5.2（权限矩阵）。

模型：app.models.handling_record.HandlingRecord。

权限要点：普通用户仅能记录/查看与本人风险事件相关的处置；管理员可查看全部。
处置操作 action 值域：ASSIGN / UPDATE_STATUS / ADD_COMMENT（数据库设计文档 v2 2.8）。
"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.dataset import Dataset
from app.models.handling_record import HandlingRecord
from app.models.risk_event import RiskEvent
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_VISIBILITY_PLATFORM,
    HANDLING_ACTIONS,
    RISK_EVENT_STATUS_TRANSITIONS,
    ROLE_SCENARIO_ADMIN,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
)
from app.utils.common import paginate, row_to_dict, validate_enum


class HandlingRecordService(ServiceBase):
    """处置记录：登记处置动作、按用户/事件查询。"""

    def _get(self, record_id: int) -> HandlingRecord:
        record = self.db.get(HandlingRecord, record_id)
        if record is None:
            raise ServiceError(404, "处置记录不存在")
        return record

    def _can_access_event(self, current_user, event: RiskEvent) -> bool:
        """Apply the same platform/scenario/personal boundary as risk events."""
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            dataset = self.db.get(Dataset, event.dataset_id)
            return bool(dataset) and self.is_platform_visibility(dataset.visibility)
        if role == ROLE_SCENARIO_ADMIN:
            dataset = self.db.get(Dataset, event.dataset_id)
            return (
                event.scenario_id == getattr(current_user, "scenario_id", None)
                and bool(dataset)
                and dataset.visibility in ("platform", "company")
            )
        if role == ROLE_SCENARIO_USER:
            return event.created_by_user_id == getattr(current_user, "id", None)
        return False

    def _can_access_record(self, current_user, record: HandlingRecord) -> bool:
        """Check the parent event before exposing a handling/audit record."""
        event = record.risk_event or self.db.get(RiskEvent, record.risk_event_id)
        return bool(event) and self._can_access_event(current_user, event)

    # ------------------------------------------------------------------
    # 新增处置记录
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user,
        risk_event_id: int,
        action: str,
        comment: str | None = None,
        status_before: str | None = None,
        status_after: str | None = None,
    ):
        """登记处置操作（USER 仅本人事件；ADMIN 全部）。

        action=UPDATE_STATUS 时必须提供 status_after（与 risk_event 状态流转配合）。

        ⚠️ 审计完整性：``status_before`` / ``status_after`` 两个入参**一律以事件真实状态为准**，
        不接受调用方自填 —— 处置记录是审计凭据，若允许调用方写入任意状态，一条 ASSIGN
        记录就能被伪造成「已处置 → 待处置」，把状态历史洗白。参数保留只为兼容签名。
        """
        self.require_login(current_user)
        event = self.db.get(RiskEvent, risk_event_id)
        if event is None:
            raise ServiceError(404, "风险事件不存在")
        if not self._can_access_event(current_user, event):
            raise ServiceError(403, "无权限操作")

        err = validate_enum(action, HANDLING_ACTIONS, "action")
        if err:
            raise ServiceError(400, err)
        # 真实前态：无论调用方传什么，都以库中事件为准
        status_before = event.status
        if action == "UPDATE_STATUS":
            # 与 RiskEventService.update_status 保持同一状态机口径（需求 5.2）：
            # 校验转换合法后同步更新事件状态，杜绝"只记日志不改状态"的旁路。
            if status_after is None:
                raise ServiceError(400, "UPDATE_STATUS 操作必须提供 status_after")
            allowed = RISK_EVENT_STATUS_TRANSITIONS.get(event.status, ())
            if status_after not in allowed:
                raise ServiceError(
                    400,
                    f"风险事件状态不允许从 {event.status} 转换到 {status_after}",
                )
            event.status = status_after
        else:
            # 其余动作不改状态：审计行的前/后态都记事件当前状态，不接受调用方自填
            status_after = event.status

        record = HandlingRecord(
            risk_event_id=risk_event_id,
            handler_id=current_user.id,
            action=action,
            status_before=status_before,
            status_after=status_after,
            comment=comment,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.commit()
        return ok(data=row_to_dict(record), message="处置记录已创建")

    # ------------------------------------------------------------------
    # 查询（USER 仅本人相关；ADMIN 全部）
    # ------------------------------------------------------------------
    @service_call
    def get_list(
        self,
        current_user,
        risk_event_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """处置记录列表。普通用户仅可见**本人风险事件**上的处置记录。"""
        self.require_login(current_user)
        stmt = select(HandlingRecord)
        role = getattr(current_user, "role", None)
        if role == ROLE_SUPER_ADMIN:
            stmt = stmt.join(RiskEvent, RiskEvent.id == HandlingRecord.risk_event_id).join(
                Dataset, Dataset.id == RiskEvent.dataset_id
            ).where(
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM
            )
        elif role == ROLE_SCENARIO_ADMIN:
            stmt = stmt.join(RiskEvent, RiskEvent.id == HandlingRecord.risk_event_id).where(
                RiskEvent.scenario_id == getattr(current_user, "scenario_id", None)
            ).join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
                Dataset.visibility.in_(("platform", "company"))
            )
        else:
            stmt = stmt.join(RiskEvent, RiskEvent.id == HandlingRecord.risk_event_id).where(
                RiskEvent.created_by_user_id == current_user.id
            )
        if risk_event_id is not None:
            stmt = stmt.where(HandlingRecord.risk_event_id == risk_event_id)
        stmt = stmt.order_by(HandlingRecord.created_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [row_to_dict(r) for r in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, record_id: int):
        """处置记录详情。"""
        self.require_login(current_user)
        record = self._get(record_id)
        if not self._can_access_record(current_user, record):
            raise ServiceError(403, "无权限操作")
        return ok(data=row_to_dict(record))

    # ------------------------------------------------------------------
    # 删除（仅 ADMIN；处置记录为审计性质，删除需谨慎）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, record_id: int):
        """删除处置记录（仅 SUPER_ADMIN，且受与查询一致的数据边界约束）。

        处置记录是审计凭据，这里刻意与 ``get`` / ``get_list`` 用同一套边界
        （:meth:`_can_access_record`）：否则「读不到的记录却能删」会成为绕过审计的旁路。
        注意：删除本身不写审计（本表无删除留痕字段），调用方需自行评估可追溯性。
        """
        self.require_admin(current_user)
        record = self._get(record_id)
        if not self._can_access_record(current_user, record):
            raise ServiceError(403, "无权限操作")
        self.db.delete(record)
        self.commit()
        return ok(message="处置记录已删除")
