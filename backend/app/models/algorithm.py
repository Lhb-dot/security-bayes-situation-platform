"""算法表 algorithm —— 开发人员注册的算法元信息。

对应《数据库设计文档v2》2.4。
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, PkType


class Algorithm(Base):
    __tablename__ = "algorithm"
    __table_args__ = (
        UniqueConstraint("code", name="uk_algorithm_code"),
    )

    id: Mapped[int] = mapped_column(PkType, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    param_schema: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    model_versions: Mapped[list["ModelVersion"]] = relationship(back_populates="algorithm")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="algorithm")
