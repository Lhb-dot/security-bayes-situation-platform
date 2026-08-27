"""报告相关请求模型（/api/v1/reports）。

对应 Service：ReportService（backend/app/services/report_service.py）。
报告类型：SCENE_SNAPSHOT（态势快照）/ USER_SNAPSHOT（用户快照），与 REPORT_TYPES 一致。
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

ReportType = Literal["SCENE_SNAPSHOT", "USER_SNAPSHOT"]
ReportFormat = Literal["markdown", "html", "pdf"]


class ReportCreate(BaseModel):
    """生成态势报告（普通用户仅本人数据）。"""

    title: str = Field(..., min_length=1, max_length=128, description="报告标题")
    report_type: ReportType = Field(..., description="报告类型")
    content: str = Field(..., min_length=1, description="报告内容")
    target_user_id: Optional[int] = Field(
        None, description="目标用户 ID（普通用户只能为空或本人）"
    )
    file_path: Optional[str] = Field(None, description="报告文件路径")
    scenario_id: Optional[int] = Field(None, description="所属场景 ID（用于场景隔离）")
    format: ReportFormat = Field("markdown", description="报告格式")
    scheduled: bool = Field(False, description="是否定时生成")
    interval_days: Optional[int] = Field(
        None, ge=1, description="定时生成周期（天），定时时必填"
    )


class ReportScheduleUpdate(BaseModel):
    """只保存定时配置；具体调度执行暂不在本接口实现。"""

    scheduled: bool = Field(..., description="是否启用定时配置")
    interval_days: Optional[int] = Field(
        None, ge=1, description="定时周期（天），启用时必填"
    )
