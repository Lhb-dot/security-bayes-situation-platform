"""态势快照表 situation_snapshot —— 定期或事件触发记录各场景的态势统计信息。

对应《数据库设计文档v2》2.9。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SituationSnapshot(Base):
    __tablename__ = "situation_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=False
    )
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_events: Mapped[int] = mapped_column(Integer, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False)
    medium_count: Mapped[int] = mapped_column(Integer, nullable=False)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_count: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    scenario: Mapped["Scenario"] = relationship(back_populates="snapshots")
