"""报告相关请求模型（/api/v1/reports）。

对应 Service：ReportService（backend/app/services/report_service.py）。
报告类型：SCENE_SNAPSHOT（态势快照）/ USER_SNAPSHOT（用户快照），与 REPORT_TYPES 一致。
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

ReportType = Literal["SCENE_SNAPSHOT", "USER_SNAPSHOT"]


class ReportCreate(BaseModel):
    """生成态势报告（普通用户仅本人数据）。"""

    report_type: ReportType = Field(..., description="报告类型")
    content: str = Field(..., min_length=1, description="报告内容")
    target_user_id: Optional[int] = Field(
        None, description="目标用户 ID（普通用户只能为空或本人）"
    )
    file_path: Optional[str] = Field(None, description="报告文件路径")
