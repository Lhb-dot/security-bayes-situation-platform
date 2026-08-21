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
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="creator")
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
