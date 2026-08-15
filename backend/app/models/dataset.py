"""数据集表 dataset —— 数据集版本信息（逻辑上同一数据集可有多个版本）。

对应《数据库设计文档v2》2.3。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Dataset(Base):
    __tablename__ = "dataset"
    __table_args__ = (
        UniqueConstraint("logical_id", "version", name="uk_dataset_logical_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    logical_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    fields_schema: Mapped[list] = mapped_column(JSONB, nullable=False)
    label_field: Mapped[str] = mapped_column(String(64), nullable=False)
    # 数据可见性分级：platform（平台）/ company（公司）/ personal（个人）
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="platform", server_default="platform"
    )
    uploader_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    uploaded_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    scenario: Mapped["Scenario"] = relationship(back_populates="datasets")
    uploader: Mapped["AppUser"] = relationship(back_populates="datasets")
    model_versions: Mapped[list["ModelVersion"]] = relationship(back_populates="dataset")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="dataset")
