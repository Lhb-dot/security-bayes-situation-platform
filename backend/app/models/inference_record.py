"""推理记录表 inference_record —— 记录每次单条样本推理的详细信息。

对应《数据库设计文档v2》2.6。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, PkType


class InferenceRecord(Base):
    __tablename__ = "inference_record"
    __table_args__ = (
        Index("idx_ir_user_time", "user_id", "executed_at"),
    )

    id: Mapped[int] = mapped_column(PkType, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("app_user.id"), nullable=False
    )
    model_version_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("model_version.id"), nullable=False
    )
    input_features: Mapped[dict] = mapped_column(JSON, nullable=False)
    prediction_label: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_risk_event: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["AppUser"] = relationship(back_populates="inference_records")
    model_version: Mapped["ModelVersion"] = relationship(
        back_populates="inference_records"
    )
    risk_event: Mapped["RiskEvent"] = relationship(
        back_populates="inference_record", uselist=False
    )
