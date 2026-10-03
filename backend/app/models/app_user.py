"""用户表 app_user —— 存储系统所有账号信息。

对应《数据库设计文档v2》2.1。PostgreSQL 保留字 user 已规避为 app_user。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("username", name="uk_app_user_username"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    # ⚠️ 本列绝不可直接序列化下发。对外一律走 row_to_dict(user, exclude=("password_hash",))，
    # 现有且仅有两处：api/v1/endpoints/auth_routes.py::_payload、
    # services/user_service.py::UserService._safe。项目没有 Pydantic 响应模型兜底
    # （接口统一是 response_model=ResponseModel，data 为 Any），新增返回用户的路径
    # 必须自己记得 exclude，否则哈希会直接进 JSON。
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # 用户-场景绑定（V3.0 §1.1.2/§1.1.6）：普通用户绑定一个场景，登录后自动确定；
    # 管理员不绑定（NULL = 可见全部场景）。
    scenario_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scenario: Mapped["Scenario"] = relationship(back_populates="users")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="uploader")
    models_trained: Mapped[list["ModelVersion"]] = relationship(
        back_populates="trainer", foreign_keys="ModelVersion.trained_by"
    )
    models_published: Mapped[list["ModelVersion"]] = relationship(
        back_populates="publisher", foreign_keys="ModelVersion.published_by"
    )
    inference_records: Mapped[list["InferenceRecord"]] = relationship(back_populates="user")
    ai_setting: Mapped["UserAISetting | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # foreign_keys 必须显式指定：risk_event 表有两条指向 app_user 的外键
    # （created_by_user_id 与 hidden_by_user_id，后者见 2026-09-27 的隐藏功能），
    # 不写 SQLAlchemy 推断不出该走哪条，mapper 初始化会直接抛 InvalidRequestError。
    risk_events: Mapped[list["RiskEvent"]] = relationship(
        back_populates="creator", foreign_keys="RiskEvent.created_by_user_id"
    )
    handling_records: Mapped[list["HandlingRecord"]] = relationship(back_populates="handler")
    reports_generated: Mapped[list["Report"]] = relationship(
        back_populates="generator", foreign_keys="Report.generated_by"
    )
    reports_targeted: Mapped[list["Report"]] = relationship(
        back_populates="target_user", foreign_keys="Report.target_user_id"
    )
    thresholds: Mapped[list["RiskThreshold"]] = relationship(
        back_populates="user", foreign_keys="RiskThreshold.user_id"
    )
    threshold_updates: Mapped[list["RiskThreshold"]] = relationship(
        back_populates="updater", foreign_keys="RiskThreshold.updated_by"
    )
    threshold_audit_logs: Mapped[list["ThresholdAuditLog"]] = relationship(
        back_populates="target_user", foreign_keys="ThresholdAuditLog.user_id"
    )
    audit_operations: Mapped[list["ThresholdAuditLog"]] = relationship(
        back_populates="operator", foreign_keys="ThresholdAuditLog.operator_id"
    )
