"""当前账号的阈值变更记录查询。"""
from sqlalchemy import select

from app.models.threshold_audit_log import ThresholdAuditLog
from app.schemas.common import ok
from app.services.base import ServiceBase, service_call
from app.services.constants import ROLE_SUPER_ADMIN
from app.utils.common import paginate, row_to_dict


class ThresholdAuditLogService(ServiceBase):
    """只返回当前登录账号作为阈值归属人的变更记录。"""

    @service_call
    def get_list(
        self,
        current_user,
        scenario_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """阈值变更日志列表（当前账号；可按场景过滤）。"""
        self.require_login(current_user)
        stmt = select(ThresholdAuditLog).where(
            ThresholdAuditLog.user_id == current_user.id
        )
        if getattr(current_user, "role", None) != ROLE_SUPER_ADMIN:
            stmt = stmt.where(
                ThresholdAuditLog.scenario_id == getattr(current_user, "scenario_id", None)
            )
        elif scenario_id is not None:
            stmt = stmt.where(ThresholdAuditLog.scenario_id == scenario_id)
        stmt = stmt.order_by(ThresholdAuditLog.operated_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [row_to_dict(log) for log in result["items"]]
        return ok(data=result)
