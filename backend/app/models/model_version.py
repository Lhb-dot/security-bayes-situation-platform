"""模型版本表 model_version —— 记录每次训练生成的模型版本。

对应《数据库设计文档v2》2.5。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, DATABASE_URL, PkType

# PostgreSQL：部分唯一索引，数据库层保证每(场景,数据集)最多一个默认模型
# SQLite：普通复合索引，唯一性由 Service 层保证
if DATABASE_URL.startswith("sqlite"):
    _mv_index = Index(
        "idx_mv_scenario_dataset_default",
        "scenario_id", "dataset_id", "is_default",
    )
else:
    _mv_index = Index(
        "uk_mv_default",
        "scenario_id", "dataset_id",
        unique=True,
        postgresql_where=text("is_default"),
    )


class ModelVersion(Base):
    __tablename__ = "model_version"
    __table_args__ = (_mv_index,)

    id: Mapped[int] = mapped_column(PkType, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("scenario.id"), nullable=False
    )
    dataset_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("dataset.id"), nullable=False
    )
    algorithm_id: Mapped[int] = mapped_column(
        PkType, ForeignKey("algorithm.id"), nullable=False
    )
    training_parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    evaluation_metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    trained_by: Mapped[int] = mapped_column(
        PkType, ForeignKey("app_user.id"), nullable=False
    )
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    published_by: Mapped[int | None] = mapped_column(
        PkType, ForeignKey("app_user.id"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
