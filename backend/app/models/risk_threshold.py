"""风险阈值配置表 risk_threshold —— 每个已接入场景的风险等级阈值。

对应《数据库设计文档v2》2.11。单值配置表（每场景一行），
主键使用业务主键 scenario_id（命名规范中明确的例外）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RiskThreshold(Base):
    __tablename__ = "risk_threshold"
    __table_args__ = (
        CheckConstraint(
            "high_threshold > medium_threshold", name="chk_rt_threshold"
        ),
    )

    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), primary_key=True
    )
    medium_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    high_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    updated_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scenario: Mapped["Scenario"] = relationship(back_populates="risk_threshold")
    updater: Mapped["AppUser"] = relationship(back_populates="threshold_updates")
