"""模型版本表 model_version —— 记录每次训练生成的模型版本。

对应《数据库设计文档v2》2.5。

推荐模型：`is_recommended` 仅表示「这是本场景推荐使用的模型」，与「默认」无关，
不设唯一约束 —— 同一（scenario_id, dataset_id）
可以同时推荐多个模型（2026-10 定稿）。
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ModelVersion(Base):
    __tablename__ = "model_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=False
    )
    dataset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dataset.id"), nullable=False
    )
    algorithm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("algorithm.id"), nullable=False
    )
    training_parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evaluation_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # 模型级的解释事实与按角色分层的 AI 措辞。这两块与任何一条推理记录都无关，
    # 可以只凭模型 ID 查看。
    model_attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_evaluation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    trained_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    published_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    scenario: Mapped["Scenario"] = relationship(back_populates="model_versions")
    dataset: Mapped["Dataset"] = relationship(back_populates="model_versions")
    algorithm: Mapped["Algorithm"] = relationship(back_populates="model_versions")
    trainer: Mapped["AppUser"] = relationship(
        back_populates="models_trained", foreign_keys=[trained_by]
    )
    publisher: Mapped["AppUser | None"] = relationship(
        back_populates="models_published", foreign_keys=[published_by]
    )
    inference_records: Mapped[list["InferenceRecord"]] = relationship(
        back_populates="model_version"
    )
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="model_version")
