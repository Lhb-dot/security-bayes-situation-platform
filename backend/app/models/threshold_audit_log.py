"""阈值变更日志表 threshold_audit_log —— 记录阈值修改历史，满足审计要求。

对应《数据库设计文档v2》2.12。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, PkType


class ThresholdAuditLog(Base):
    __tablename__ = "threshold_audit_log"

    id: Mapped[int] = mapped_column(PkType, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("scenario.id"), nullable=False
    )
    operator_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("app_user.id"), nullable=False
    )
    old_medium: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    new_medium: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    old_high: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    new_high: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    operated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scenario: Mapped["Scenario"] = relationship(back_populates="audit_logs")
    operator: Mapped["AppUser"] = relationship(back_populates="audit_operations")
