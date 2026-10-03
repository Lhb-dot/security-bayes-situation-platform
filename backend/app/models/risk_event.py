"""风险事件表 risk_event —— 由推理结果生成的风险事件。

对应《数据库设计文档v2》2.7。冗余字段（original_label / risk_type / risk_level /
risk_score / dataset_version / raw_features）来源于主表，仅为查询展示与跨场景统计，
写入时与来源保持一致，避免联表。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RiskEvent(Base):
    __tablename__ = "risk_event"
    __table_args__ = (
        Index("idx_re_user_scenario_status", "created_by_user_id", "scenario_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inference_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inference_record.id"), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=False
    )
    dataset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dataset.id"), nullable=False
    )
    dataset_version: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("algorithm.id"), nullable=False
    )
    model_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("model_version.id"), nullable=False
    )
    original_label: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # 航母甲板热点图坐标（V3.0 §7.4.1）：仅航母场景非空，其余场景为 NULL
    fault_position_x: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    fault_position_y: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    # 「隐藏」（软删除，2026-09-27）：需求 5.2 禁止真删（历史事件必须保持可追溯），
    # 所以列表用可见性开关 —— hidden_at 非空 = 已隐藏。数据、处置记录、统计口径都不受影响。
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=True
    )

    inference_record: Mapped["InferenceRecord"] = relationship(
        back_populates="risk_event"
    )
    # 必须显式指定外键：本表有 created_by_user_id / hidden_by_user_id 两条指向 app_user
    creator: Mapped["AppUser"] = relationship(
        back_populates="risk_events", foreign_keys=[created_by_user_id]
    )
    scenario: Mapped["Scenario"] = relationship(back_populates="risk_events")
    dataset: Mapped["Dataset"] = relationship(back_populates="risk_events")
    algorithm: Mapped["Algorithm"] = relationship(back_populates="risk_events")
    model_version: Mapped["ModelVersion"] = relationship(back_populates="risk_events")
    handling_records: Mapped[list["HandlingRecord"]] = relationship(
        back_populates="risk_event"
    )
