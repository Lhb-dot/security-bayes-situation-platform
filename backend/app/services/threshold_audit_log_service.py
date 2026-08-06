"""阈值变更日志 Service（ThresholdAuditLog）。

对应需求文档章节：5.4.1.5（变更记录：每次修改必须保留变更记录，至少包含
管理员账号ID、场景ID、修改时间、修改前数值和修改后数值）。

模型：app.models.threshold_audit_log.ThresholdAuditLog。

说明：本表的写入由 risk_threshold_service.update 在阈值变更时自动触发；
本 Service 仅提供只读查询（审计用途，仅 ADMIN 可访问）。
"""
from typing import Optional

from sqlalchemy import select

from app.models.threshold_audit_log import ThresholdAuditLog
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.utils.common import get_logger, paginate, row_to_dict

logger = get_logger("threshold_audit_log")


class ThresholdAuditLogService(ServiceBase):
    """阈值变更审计日志查询（仅 ADMIN）。"""

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
        """阈值变更日志列表（仅 ADMIN；可按场景过滤）。"""
        self.require_admin(current_user)
        stmt = select(ThresholdAuditLog)
        if scenario_id is not None:
            stmt = stmt.where(ThresholdAuditLog.scenario_id == scenario_id)
        stmt = stmt.order_by(ThresholdAuditLog.operated_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [row_to_dict(log) for log in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, log_id: int):
        """审计日志详情（仅 ADMIN）。"""
        self.require_admin(current_user)
        log = self._get(log_id)
        return ok(data=row_to_dict(log))
