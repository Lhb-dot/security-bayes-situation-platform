"""报告 Service（Report）—— 对应需求中的"实验记录/报表"。

对应需求文档章节：6.2（报告生成 P1）、6.8.5（报告数据范围）。

模型：app.models.report.Report。

说明：ORM 中没有 ExperimentLog 表；需求文档中的"报告生成"（态势报告）由
report 表承载，此处 ReportService 即"实验记录/报表"能力的实现。

业务规则（需求 6.8.5）：
1. 普通用户生成报告时只能使用本人数据 → target_user_id 只能为空（本人）或等于本人。
2. 管理员生成报告时可以选择全平台（target_user_id=None）或指定用户数据。
3. 普通用户查看报告：本人生成的或定向给自己的（target_user_id == 本人）。
4. 管理员可查看全部报告，并按 target_user_id 过滤。
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import false, or_, select

from app.models.app_user import AppUser
from app.models.report import Report
from app.schemas.common import ok
from app.services.base import ServiceBase, ServiceError, service_call
from app.services.constants import (
    REPORT_FORMATS,
    REPORT_TYPES,
    ROLE_SCENARIO_ADMIN,
    ROLE_SUPER_ADMIN,
)
from app.utils.common import (
    get_logger,
    paginate,
    row_to_dict,
    validate_enum,
    validate_required,
)

logger = get_logger("report")


class ReportService(ServiceBase):
    """报告生成（P1）/ 查询 / 删除。"""

    def _get(self, report_id: int) -> Report:
        report = self.db.get(Report, report_id)
        if report is None:
            raise ServiceError(404, "报告不存在")
        return report

    @staticmethod
    def _can_view(user, report: Report) -> bool:
        return (
            report.generated_by == user.id
            or report.target_user_id == user.id
        )

    # ------------------------------------------------------------------
    # 生成（需求 6.8.5：报告数据范围）
    # ------------------------------------------------------------------
    @service_call
    def create(
        self,
        current_user,
        report_type: str,
        content: str,
        target_user_id: Optional[int] = None,
        file_path: Optional[str] = None,
        scenario_id: Optional[int] = None,
        format: str = "markdown",
        scheduled: bool = False,
        interval_days: Optional[int] = None,
    ):
        """生成态势报告。

        - 普通用户：只能基于本人数据（target_user_id 必须为空或本人），否则 403。
        - 系统管理员：可生成全平台或指定用户报告，可指定任意场景。
        - 场景管理员/用户：scenario_id 强制为本人绑定场景。
        - 格式 / 定时：format 取值 markdown/html/pdf；定时时 interval_days 必填。
        """
        self.require_login(current_user)
        err = validate_enum(report_type, REPORT_TYPES, "report_type")
        if err:
            raise ServiceError(400, err)
        err = validate_enum(format, REPORT_FORMATS, "format")
        if err:
            raise ServiceError(400, err)
        err = validate_required({"content": content}, ("content",))
        if err:
            raise ServiceError(400, err)
        if scheduled and (interval_days is None or interval_days < 1):
            raise ServiceError(400, "定时生成需指定有效周期（至少 1 天）")

        role = getattr(current_user, "role", None)
        if role != ROLE_SUPER_ADMIN:
            # 场景角色只能生成本人绑定场景的报告。
            if scenario_id is not None and scenario_id != current_user.scenario_id:
                raise ServiceError(403, "只能生成本人绑定场景的报告")
            scenario_id = current_user.scenario_id
            if role == ROLE_SCENARIO_USER and target_user_id is not None and target_user_id != current_user.id:
                raise ServiceError(403, "普通用户只能基于本人数据生成报告")
            if role == ROLE_SCENARIO_ADMIN and target_user_id is not None:
                target = self.db.get(AppUser, target_user_id)
                if target is None:
                    raise ServiceError(404, "目标用户不存在")
                if target.scenario_id != scenario_id:
                    raise ServiceError(403, "只能指定本人绑定场景内的用户")
        elif target_user_id is not None:
            target = self.db.get(AppUser, target_user_id)
            if target is None:
                raise ServiceError(404, "目标用户不存在")

        report = Report(
            generated_by=current_user.id,
            report_type=report_type,
            target_user_id=target_user_id,
            content=content,
            file_path=file_path,
            scenario_id=scenario_id,
            format=format,
            scheduled=scheduled,
            interval_days=interval_days if scheduled else None,
            generated_at=datetime.now(timezone.utc),
        )
        self.db.add(report)
        self.commit()
        return ok(data=row_to_dict(report), message="报告已生成")

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @service_call
    def get_list(
        self,
        current_user,
        target_user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
    ):
        """报告列表（按三级角色隔离）。

        系统管理员：全部报告，可按 target_user_id 过滤；
        场景管理员：自己绑定场景下的报告；
        场景用户：本人生成的或定向给自己的报告。
        """
        self.require_login(current_user)
        role = getattr(current_user, "role", None)
        stmt = select(Report)
        if role == ROLE_SUPER_ADMIN:
            if target_user_id is not None:
                stmt = stmt.where(Report.target_user_id == target_user_id)
        elif role == ROLE_SCENARIO_ADMIN:
            scid = getattr(current_user, "scenario_id", None)
            if scid is None:
                stmt = stmt.where(false())  # 未绑定场景：看不到任何报告
            else:
                stmt = stmt.where(Report.scenario_id == scid)
        else:
            stmt = stmt.where(
                or_(
                    Report.generated_by == current_user.id,
                    Report.target_user_id == current_user.id,
                )
            )
        stmt = stmt.order_by(Report.generated_at.desc())
        result = paginate(self.db, stmt, page, page_size)
        result["items"] = [row_to_dict(r) for r in result["items"]]
        return ok(data=result)

    @service_call
    def get(self, current_user, report_id: int):
        """报告详情（普通用户仅本人生成或定向给自己的报告）。"""
        self.require_login(current_user)
        report = self._get(report_id)
        role = getattr(current_user, "role", None)
        if role == ROLE_SCENARIO_ADMIN and report.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        if role not in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN) and not self._can_view(current_user, report):
            raise ServiceError(403, "无权限操作")
        return ok(data=row_to_dict(report))

    # ------------------------------------------------------------------
    # 删除（生成者本人或 ADMIN）
    # ------------------------------------------------------------------
    @service_call
    def delete(self, current_user, report_id: int):
        """删除报告：生成者本人或管理员。"""
        self.require_login(current_user)
        report = self._get(report_id)
        role = getattr(current_user, "role", None)
        if role == ROLE_SCENARIO_ADMIN and report.scenario_id != getattr(current_user, "scenario_id", None):
            raise ServiceError(403, "无权限操作")
        if role not in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN) and report.generated_by != current_user.id:
            raise ServiceError(403, "无权限操作")
        self.db.delete(report)
        self.commit()
        return ok(message="报告已删除")
