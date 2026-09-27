"""报告相关请求模型（/api/v1/reports）。

对应 Service：ReportService（backend/app/services/report_service.py）。
报告类型：SCENE_SNAPSHOT（态势快照）/ USER_SNAPSHOT（用户快照），与 REPORT_TYPES 一致。
"""
from typing import Literal

from pydantic import BaseModel, Field

ReportType = Literal["SCENE_SNAPSHOT", "USER_SNAPSHOT"]
ReportFormat = Literal["markdown", "html", "pdf"]


class ReportCreate(BaseModel):
    """生成态势报告（普通用户仅本人数据）。"""

    title: str = Field(..., min_length=1, max_length=128, description="报告标题")
    report_type: ReportType = Field(..., description="报告类型")
    content: str = Field(..., min_length=1, description="报告内容")
    file_path: str | None = Field(None, description="报告文件路径")
    scenario_id: int | None = Field(None, description="所属场景 ID（用于场景隔离）")
    format: ReportFormat = Field("markdown", description="报告格式")
    scheduled: bool = Field(False, description="是否定时生成")
    interval_days: int | None = Field(
        None, ge=1, description="定时生成周期（天），定时时必填"
    )


class ReportScheduleUpdate(BaseModel):
    """只保存定时配置；到期后由后台调度器原地重新生成该报告。"""

    scheduled: bool = Field(..., description="是否启用定时配置")
    interval_days: int | None = Field(
        None, ge=1, description="定时周期（天），启用时必填"
    )


class ReportGenerate(BaseModel):
    """自动生成态势报告（服务端基于真实数据 + 算法解释组装内容）。

    数据范围只区分聚合数据与本人个人数据，不再支持指定单个用户。
    scheduled=True 时这条报告同时登记为定时报告：立刻产出内容，
    并把下次生成时刻写入 next_run_at，到期由后台调度器重新生成。
    """

    title: str = Field(..., min_length=1, max_length=128, description="报告标题")
    scenario_id: int | None = Field(
        None, description="所属场景 ID（非超管强制为本人绑定场景）"
    )
    scope: Literal["self", "all"] = Field(
        "self", description="数据范围：self=本人个人数据；all=全平台/本场景聚合数据"
    )
    format: ReportFormat = Field("markdown", description="报告格式")
    scheduled: bool = Field(False, description="是否登记为定时报告")
    interval_days: int | None = Field(
        None, ge=1, description="定时周期（天），scheduled=True 时必填"
    )
