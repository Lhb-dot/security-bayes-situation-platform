"""当前账号的阈值变更记录查询。"""
from typing import Optional

from sqlalchemy import select

from app.models.threshold_audit_log import ThresholdAuditLog
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.utils.common import get_logger, paginate, row_to_dict

logger = get_logger("threshold_audit_log")


class ThresholdAuditLogService(ServiceBase):
    """只返回当前登录账号作为阈值归属人的变更记录。"""

    def _get(self, log_id: int) -> ThresholdAuditLog:
        log = self.db.get(ThresholdAuditLog, log_id)
        if log is None:
            raise ServiceError(404, "审计日志不存在")
        return log

    @service_call
    def get_list(
        self,
        current_user,
        scenario_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """阈值变更日志列表（当前账号；可按场景过滤）。"""
        self.require_login(current_user)
        stmt = select(ThresholdAuditLog).where(
            ThresholdAuditLog.user_id == current_user.id
        )
        if getattr(current_user, "role", None) != "SUPER_ADMIN":
            stmt = stmt.where(ThresholdAuditLog.scenario_id == current_user.scenario_id)
        elif scenario_id is not None:
            stmt = stmt.where(ThresholdAuditLog.scenario_id == scenario_id)
        stmt = stmt.order_by(ThresholdAuditLog.operated_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [row_to_dict(log) for log in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, log_id: int):
        """审计日志详情（当前账号）。"""
        self.require_login(current_user)
        log = self.db.scalar(
            select(ThresholdAuditLog).where(
                ThresholdAuditLog.id == log_id,
                ThresholdAuditLog.user_id == current_user.id,
            )
        )
        if log is None:
            raise ServiceError(404, "审计日志不存在")
        return ok(data=row_to_dict(log))
