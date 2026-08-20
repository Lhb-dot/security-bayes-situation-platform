"""风险阈值配置表 risk_threshold —— 每个账号在场景下的风险等级阈值。

同一个场景允许不同账号使用不同阈值，因此以 user_id + scenario_id 为业务主键。
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

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), primary_key=True
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

    user: Mapped["AppUser"] = relationship(
        back_populates="thresholds", foreign_keys=[user_id]
    )
    scenario: Mapped["Scenario"] = relationship(back_populates="risk_thresholds")
    updater: Mapped["AppUser"] = relationship(
        back_populates="threshold_updates", foreign_keys=[updated_by]
    )
