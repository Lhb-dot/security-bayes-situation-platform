"""报告表 report —— 存储用户生成的态势报告。

对应《数据库设计文档v2》2.10。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    generated_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    generator: Mapped["AppUser"] = relationship(
        back_populates="reports_generated", foreign_keys=[generated_by]
    )
    target_user: Mapped["AppUser | None"] = relationship(
        back_populates="reports_targeted", foreign_keys=[target_user_id]
    )
