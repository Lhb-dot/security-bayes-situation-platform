"""按账号和场景维护风险阈值，并记录每次修改。"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.models.risk_threshold import RiskThreshold
from app.models.scenario import Scenario
from app.models.threshold_audit_log import ThresholdAuditLog
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.utils.common import get_logger, row_to_dict

logger = get_logger("risk_threshold")


class RiskThresholdService(ServiceBase):
    """风险阈值：配置归属当前账号，场景管理员只可操作绑定场景。"""

    def _get_for_user(self, user_id: int, scenario_id: int) -> Optional[RiskThreshold]:
        return self.db.scalar(
            select(RiskThreshold).where(
                RiskThreshold.user_id == user_id,
                RiskThreshold.scenario_id == scenario_id,
            )
        )

    @service_call
    def get_list(self, current_user):
        """查询当前账号可见的全部阈值配置。"""
        self.require_login(current_user)
        stmt = (
            select(RiskThreshold)
            .where(RiskThreshold.user_id == current_user.id)
            .join(Scenario, Scenario.id == RiskThreshold.scenario_id)
        )
        if getattr(current_user, "role", None) != "SUPER_ADMIN":
            stmt = stmt.where(RiskThreshold.scenario_id == current_user.scenario_id)
        rows = self.db.scalars(stmt.order_by(RiskThreshold.scenario_id)).all()
        return ok(data=[row_to_dict(row) for row in rows])

    @service_call
    def get_by_scenario(self, current_user, scenario_id: int):
        """按场景查询阈值（登录用户可读，供态势/推理结果展示；需求 5.4.1.3）。

        必须校验场景绑定：非 SUPER_ADMIN 仅可读本人绑定场景阈值。
        """
        self.require_scenario_access(current_user, scenario_id)
        threshold = self._get_for_user(current_user.id, scenario_id)
        if threshold is None:
            return ok(data=None, message="该账号尚未配置该场景风险阈值")
        return ok(data=row_to_dict(threshold))

    @service_call
    def update(
        self,
        current_user,
        scenario_id: int,
        medium_threshold: float,
        high_threshold: float,
    ):
        """更新当前账号在指定场景的阈值。

        - 校验 0 <= medium < high <= 1（需求 5.4.1.2）；
        - 按 user_id + scenario_id upsert（无行则插入）；
        - 写 threshold_audit_log 审计。
        """
        self.require_scenario_access(current_user, scenario_id)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")

        medium = round(float(medium_threshold), 2)
        high = round(float(high_threshold), 2)
        if not (0 <= medium <= 1) or not (0 <= high <= 1):
            raise ServiceError(400, "阈值必须在 [0,1] 范围内")
        if high <= medium:
            raise ServiceError(400, "high_threshold 必须大于 medium_threshold")

        threshold = self._get_for_user(current_user.id, scenario_id)
        old_medium = float(threshold.medium_threshold) if threshold else medium
        old_high = float(threshold.high_threshold) if threshold else high

        now = datetime.now(timezone.utc)
        if threshold is None:
            threshold = RiskThreshold(
                user_id=current_user.id,
                scenario_id=scenario_id,
                medium_threshold=medium,
                high_threshold=high,
                updated_by=current_user.id,
                updated_at=now,
            )
            self.db.add(threshold)
        else:
            threshold.medium_threshold = medium
            threshold.high_threshold = high
            threshold.updated_by = current_user.id
            threshold.updated_at = now

        # 首次配置时旧值记为新值，表示“从无到有”。
        audit = ThresholdAuditLog(
            user_id=current_user.id,
            scenario_id=scenario_id,
            operator_id=current_user.id,
            old_medium=old_medium,
            new_medium=medium,
            old_high=old_high,
            new_high=high,
            operated_at=now,
        )
        self.db.add(audit)
        self.commit()
        return ok(
            data=row_to_dict(threshold),
            message="风险阈值已更新并记录审计日志",
        )