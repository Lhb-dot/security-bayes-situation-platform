"""报告表 report —— 存储用户生成的态势报告。

对应《数据库设计文档v2》2.10。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    generated_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="未命名报告")
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=True
    )
    scenario_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 结构化报告数据（统计 + 算法解释 + NL 分析），供前端渲染图表与溯源
    report_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="markdown")
    scheduled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    generator: Mapped["AppUser"] = relationship(
        back_populates="reports_generated", foreign_keys=[generated_by]
    )
    target_user: Mapped["AppUser | None"] = relationship(
        back_populates="reports_targeted", foreign_keys=[target_user_id]
    )
