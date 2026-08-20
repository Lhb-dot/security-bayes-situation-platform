"""阈值变更日志表 threshold_audit_log —— 记录阈值修改历史，满足审计要求。

对应《数据库设计文档v2》2.12。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ThresholdAuditLog(Base):
    __tablename__ = "threshold_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=False
    )
    operator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    old_medium: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    new_medium: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    old_high: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    new_high: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    operated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    target_user: Mapped["AppUser"] = relationship(
        back_populates="threshold_audit_logs", foreign_keys=[user_id]
    )
    scenario: Mapped["Scenario"] = relationship(back_populates="audit_logs")
    operator: Mapped["AppUser"] = relationship(
        back_populates="audit_operations", foreign_keys=[operator_id]
    )