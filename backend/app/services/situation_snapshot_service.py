"""态势快照 Service（SituationSnapshot）+ 个人/全局态势统计。

对应需求文档章节：6.2（态势展示 P0）、6.8（数据访问与态势统计规则）、
5.2（风险事件统计口径）。

模型：app.models.situation_snapshot.SituationSnapshot。

业务规则（需求 6.8）：
1. 普通用户态势页面只统计本人数据（compute_user_stats，动态统计本人风险事件）。
2. 系统管理员态势仅统计 platform 派生事件与运维聚合（compute_scene_stats），并可按场景过滤。
3. 快照表（situation_snapshot）为定期/事件触发的场景级统计落库，仅 ADMIN 或
   定时任务写入；登录用户可读取用于展示。
4. 未接入场景不得使用虚构数据（需求 6.2 态势展示）——统计一律基于真实 RiskEvent。
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.models.dataset import Dataset
from app.models.risk_event import RiskEvent
from app.models.scenario import Scenario
from app.models.situation_snapshot import SituationSnapshot
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    DATASET_VISIBILITY_PLATFORM,
    RISK_EVENT_STATUS_PENDING,
    RISK_EVENT_STATUS_PROCESSING,
    RISK_EVENT_STATUS_RESOLVED,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    ROLE_SCENARIO_USER,
    ROLE_SUPER_ADMIN,
)
from app.utils.common import get_logger, paginate, row_to_dict

logger = get_logger("situation_snapshot")


class SituationSnapshotService(ServiceBase):
    """态势快照管理 + 个人/全局态势统计。"""

    # ------------------------------------------------------------------
    # 统计（需求 6.8：口径按风险等级与处置状态）
    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate(events) -> dict:
        total = len(events)
        return {
            "total_events": total,
            "high_count": sum(1 for e in events if e.risk_level == RISK_LEVEL_HIGH),
            "medium_count": sum(1 for e in events if e.risk_level == RISK_LEVEL_MEDIUM),
            "low_count": sum(1 for e in events if e.risk_level == RISK_LEVEL_LOW),
            "pending_count": sum(1 for e in events if e.status == RISK_EVENT_STATUS_PENDING),
            "processing_count": sum(1 for e in events if e.status == RISK_EVENT_STATUS_PROCESSING),
            "resolved_count": sum(1 for e in events if e.status == RISK_EVENT_STATUS_RESOLVED),
        }

    @service_call
    def compute_user_stats(self, current_user):
        """个人态势（需求 6.8.1：普通用户只统计本人数据，后端强制按用户过滤）。"""
        self.require_login(current_user)
        events = self.db.scalars(
            select(RiskEvent).where(
                RiskEvent.created_by_user_id == current_user.id
            )
        ).all()
        return ok(data=self._aggregate(events))

    @service_call
    def compute_scene_stats(
        self, current_user, scenario_id: Optional[int] = None
    ):
        """平台总览态势（需求 0.2 / 6.8.3 / 6.11）。

        SUPER_ADMIN 仅统计 platform 数据集派生的风险事件，不含公司/个人派生数据。
        """
        self.require_admin(current_user)
        stmt = (
            select(RiskEvent)
            .join(Dataset, Dataset.id == RiskEvent.dataset_id)
            .where(Dataset.visibility == DATASET_VISIBILITY_PLATFORM)
        )
        if scenario_id is not None:
            stmt = stmt.where(RiskEvent.scenario_id == scenario_id)
        events = self.db.scalars(stmt).all()
        return ok(data=self._aggregate(events))

    @service_call
    def get_scene_situation(self, current_user, scenario_id: int):
        """场景态势（动态统计 + 最近风险事件），供场景大屏使用。

        返回 {scenario_id, stats, recent_events}：
        - stats：按风险等级/处置状态聚合的真实计数（口径同 _aggregate）；
        - recent_events：最近 20 条真实风险事件（按发生时间倒序）。
        """
        self.require_scenario_access(current_user, scenario_id)
        role = getattr(current_user, "role", None)
        stmt = select(RiskEvent).where(RiskEvent.scenario_id == scenario_id)
        if role == ROLE_SUPER_ADMIN:
            stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM
            )
        elif role == ROLE_SCENARIO_USER:
            # 普通用户态势只统计本人数据（需求 6.8.1，后端强制按用户过滤）
            stmt = stmt.where(RiskEvent.created_by_user_id == current_user.id)
        events = self.db.scalars(stmt).all()
        recent = sorted(events, key=lambda e: e.occurred_at or datetime(1970, 1, 1), reverse=True)[:20]
        return ok(
            data={
                "scenario_id": scenario_id,
                "stats": self._aggregate(events),
                "recent_events": [row_to_dict(e) for e in recent],
            }
        )

    # ------------------------------------------------------------------
    # 快照落库（仅 ADMIN / 定时任务；场景级统计）
    # ------------------------------------------------------------------
    @service_call
    def create_snapshot(self, current_user, scenario_id: int):
        """生成场景态势快照并落库（管理级角色；SUPER_ADMIN 仅统计 platform 派生事件）。

        注意：SituationSnapshot 表只有 pending_count/resolved_count 列（无
        processing_count），"处理中"口径仅出现在动态统计（compute_*）中，不落库。
        """
        self.require_scenario_admin_of(current_user, scenario_id)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ServiceError(404, "场景不存在")
        stmt = select(RiskEvent).where(RiskEvent.scenario_id == scenario_id)
        if getattr(current_user, "role", None) == ROLE_SUPER_ADMIN:
            stmt = stmt.join(Dataset, Dataset.id == RiskEvent.dataset_id).where(
                Dataset.visibility == DATASET_VISIBILITY_PLATFORM
            )
        events = self.db.scalars(stmt).all()
        stats = self._aggregate(events)
        snapshot = SituationSnapshot(
            scenario_id=scenario_id,
            snapshot_time=datetime.now(timezone.utc),
            total_events=stats["total_events"],
            high_count=stats["high_count"],
            medium_count=stats["medium_count"],
            low_count=stats["low_count"],
            pending_count=stats["pending_count"],
            resolved_count=stats["resolved_count"],
            extra_data=None,
        )
        self.db.add(snapshot)
        self.commit()
        return ok(data=row_to_dict(snapshot), message="态势快照已生成")

    # ------------------------------------------------------------------
    # 查询（登录用户可读）
    # ------------------------------------------------------------------
    @service_call
    def get_latest(self, current_user, scenario_id: int):
        """最近一次场景态势快照。"""
        self.require_scenario_access(current_user, scenario_id)
        snapshot = self.db.scalar(
            select(SituationSnapshot)
            .where(SituationSnapshot.scenario_id == scenario_id)
            .order_by(SituationSnapshot.snapshot_time.desc())
        )
        if snapshot is None:
            return ok(data=None, message="该场景暂无态势快照")
        return ok(data=row_to_dict(snapshot))

    @service_call
    def get_list(
        self,
        current_user,
        scenario_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """态势快照列表（按场景过滤可选；非 SUPER_ADMIN 强制绑定场景）。"""
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        stmt = select(SituationSnapshot)
        if role == ROLE_SUPER_ADMIN:
            if scenario_id is not None:
                stmt = stmt.where(SituationSnapshot.scenario_id == scenario_id)
        else:
            bound = getattr(current_user, "scenario_id", None)
            if bound is None:
                return ok(data={"items": [], "total": 0, "page": page, "page_size": page_size})
            if scenario_id is not None and scenario_id != bound:
                raise ServiceError(403, "无权限操作")
            stmt = stmt.where(SituationSnapshot.scenario_id == bound)
        stmt = stmt.order_by(SituationSnapshot.snapshot_time.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [row_to_dict(s) for s in result["items"]]
        return ok(data=result)
