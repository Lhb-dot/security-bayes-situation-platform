"""处置记录表 handling_record —— 记录对风险事件的处置操作。

对应《数据库设计文档v2》2.8。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, PkType


class HandlingRecord(Base):
    __tablename__ = "handling_record"

    id: Mapped[int] = mapped_column(PkType, primary_key=True, autoincrement=True)
    risk_event_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("risk_event.id"), nullable=False
    )
    handler_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("app_user.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status_before: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status_after: Mapped[str | None] = mapped_column(String(16), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    risk_event: Mapped["RiskEvent"] = relationship(back_populates="handling_records")
    handler: Mapped["AppUser"] = relationship(back_populates="handling_records")
