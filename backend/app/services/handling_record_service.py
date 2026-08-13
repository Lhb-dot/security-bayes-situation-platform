"""处置记录 Service（HandlingRecord）。

对应需求文档章节：4（风险结果统一为 RiskEvent 后跟进处置）、5.2（处置状态流转）、
6.5.2（权限矩阵）。

模型：app.models.handling_record.HandlingRecord。

权限要点：普通用户仅能记录/查看与本人风险事件相关的处置；管理员可查看全部。
处置操作 action 值域：ASSIGN / UPDATE_STATUS / ADD_COMMENT（数据库设计文档 v2 2.8）。
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select

from app.models.handling_record import HandlingRecord
from app.models.risk_event import RiskEvent
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    HANDLING_ACTIONS,
    RISK_EVENT_STATUS_TRANSITIONS,
    ROLE_ADMIN,
)
from app.utils.common import get_logger, paginate, row_to_dict, validate_enum

logger = get_logger("handling_record")


class HandlingRecordService(ServiceBase):
    """处置记录：登记处置动作、按用户/事件查询。"""

    def _get(self, record_id: int) -> HandlingRecord:
        record = self.db.get(HandlingRecord, record_id)
        if record is None:
            raise ServiceError(404, "处置记录不存在")
        return record

    @staticmethod
    def _is_related(record: HandlingRecord, user) -> bool:
        """判断处置记录是否与当前用户相关（本人处置或本人事件）。"""
        return (
            record.handler_id == user.id
            or record.risk_event.created_by_user_id == user.id
        )

    # ------------------------------------------------------------------
    # 新增处置记录
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user,
        risk_event_id: int,
        action: str,
        comment: Optional[str] = None,
        status_before: Optional[str] = None,
        status_after: Optional[str] = None,
    ):
        """登记处置操作（USER 仅本人事件；ADMIN 全部）。

        action=UPDATE_STATUS 时必须提供 status_after（与 risk_event 状态流转配合）。
        """
        self.require_login(current_user)
        event = self.db.get(RiskEvent, risk_event_id)
        if event is None:
            raise ServiceError(404, "风险事件不存在")
        self.require_owner_or_admin(current_user, event.created_by_user_id)

        err = validate_enum(action, HANDLING_ACTIONS, "action")
        if err:
            raise ServiceError(400, err)
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
            status_before = status_before or event.status
            event.status = status_after

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
        risk_event_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """处置记录列表。普通用户仅可见本人处置的或本人风险事件的记录。"""
        self.require_login(current_user)
        stmt = select(HandlingRecord)
        if getattr(current_user, "role", None) != ROLE_ADMIN:
            stmt = stmt.join(
                RiskEvent, RiskEvent.id == HandlingRecord.risk_event_id
            ).where(
                or_(
                    HandlingRecord.handler_id == current_user.id,
                    RiskEvent.created_by_user_id == current_user.id,
                )
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
        if (
            getattr(current_user, "role", None) != ROLE_ADMIN
            and not self._is_related(record, current_user)
        ):
            raise ServiceError(403, "无权限操作")
        return ok(data=row_to_dict(record))

    # ------------------------------------------------------------------
    # 删除（仅 ADMIN；处置记录为审计性质，删除需谨慎）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, record_id: int):
        """删除处置记录（仅 ADMIN）。"""
        self.require_admin(current_user)
        record = self._get(record_id)
        self.db.delete(record)
        self.commit()
        return ok(message="处置记录已删除")
