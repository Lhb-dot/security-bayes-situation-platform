"""风险阈值配置 Service（RiskThreshold）。

对应需求文档章节：5.4（风险等级生成规则）、5.4.1（风险阈值配置管理规范）、
6.5.2（权限矩阵：修改风险阈值 → 仅管理员）。

模型：app.models.risk_threshold.RiskThreshold（单值表，scenario_id 为主键，每场景一行）。

业务规则（需求 5.4.1）：
1. 场景隔离：各场景分别维护阈值，禁止共用（网络与电力分别维护；航母第一阶段仅预留
   配置能力，不启用实际阈值计算——启用与否由上层调用方决定）。
2. 两项阈值均位于 [0,1]，且 high_threshold > medium_threshold（DB 层 chk_rt_threshold 兜底）。
3. 阈值绑定 scenario_id 持久化，支持按场景查询和修改。
4. 修改成功后立即生效（后续推理直接读取最新值，无需重启；本表即运行时配置源）。
5. 每次修改必须保留变更记录：操作人、场景、时间、修改前后数值（写 threshold_audit_log）。
"""
from datetime import datetime, timezone
from typing import Optional

from app.models.risk_threshold import RiskThreshold
from app.models.scenario import Scenario
from app.models.threshold_audit_log import ThresholdAuditLog
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.utils.common import get_logger, row_to_dict

logger = get_logger("risk_threshold")


class RiskThresholdService(ServiceBase):
    """场景风险阈值：查询（登录用户）/ 修改（仅 ADMIN，含审计）。"""

    @service_call
    def get_by_scenario(self, current_user, scenario_id: int):
        """按场景查询阈值（登录用户可读，供态势/推理结果展示；需求 5.4.1.3）。"""
        self.require_login(current_user)
        threshold = self.db.get(RiskThreshold, scenario_id)
        if threshold is None:
            return ok(data=None, message="该场景尚未配置风险阈值")
        return ok(data=row_to_dict(threshold))

    @service_call
    def update(
        self,
        current_user,
        scenario_id: int,
        medium_threshold: float,
        high_threshold: float,
    ):
        """更新场景阈值（管理级角色，场景管理员仅自己场景）。

        - 校验 0 <= medium < high <= 1（需求 5.4.1.2）；
        - 单值表 upsert（无行则插入）；
        - 写 threshold_audit_log 审计（需求 5.4.1.5：操作人不得为空）。
        """
        self.require_scenario_admin_of(current_user, scenario_id)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")

        medium = float(medium_threshold)
        high = float(high_threshold)
        if not (0 <= medium <= 1) or not (0 <= high <= 1):
            raise ServiceError(400, "阈值必须在 [0,1] 范围内")
        if high <= medium:
            raise ServiceError(400, "high_threshold 必须大于 medium_threshold")

        threshold = self.db.get(RiskThreshold, scenario_id)
        old_medium = float(threshold.medium_threshold) if threshold else None
        old_high = float(threshold.high_threshold) if threshold else None

        now = datetime.now(timezone.utc)
        if threshold is None:
            threshold = RiskThreshold(
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

        # 审计日志（首次配置时旧值记为新值，表示"从无到有"）
        audit = ThresholdAuditLog(
            scenario_id=scenario_id,
            operator_id=current_user.id,
            old_medium=old_medium if old_medium is not None else medium,
            new_medium=medium,
            old_high=old_high if old_high is not None else high,
            new_high=high,
            operated_at=now,
        )
        self.db.add(audit)
        self.commit()
        return ok(
            data=row_to_dict(threshold),
            message="风险阈值已更新并记录审计日志",
        )
