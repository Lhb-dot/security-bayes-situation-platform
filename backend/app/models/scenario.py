"""场景表 scenario —— 系统支持的三个场景及其状态。

对应《数据库设计文档v2》2.2。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Scenario(Base):
    __tablename__ = "scenario"
    __table_args__ = (
        UniqueConstraint("code", name="uk_scenario_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="scenario")
    model_versions: Mapped[list["ModelVersion"]] = relationship(back_populates="scenario")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="scenario")
    snapshots: Mapped[list["SituationSnapshot"]] = relationship(back_populates="scenario")
    risk_threshold: Mapped["RiskThreshold"] = relationship(back_populates="scenario")
    audit_logs: Mapped[list["ThresholdAuditLog"]] = relationship(back_populates="scenario")
