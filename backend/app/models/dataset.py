"""数据集表 dataset —— 数据集版本信息（逻辑上同一数据集可有多个版本）。

对应《数据库设计文档v2》2.3。

迭代模型（见 app/services/dataset_iteration.py）：
- 每一行 = 一个**版本快照**；`version` 在 logical_id 内单调递增。
- `change_type` 记录这一版是怎么来的（初次登记 / 字段变更 / 追加样本 …），
  由 DatasetService 在生成版本时写入，原地迭代不会改写它。
- `base_version_id` 记录血缘：本版从哪一版迭代而来，便于回溯「加了什么」。
- `is_breaking` 标记本版是否破坏结构兼容（旧模型能否继续复用）。
  追加样本这类兼容迭代为 False，字段/标签变更为 True。
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
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
    # 自填名（上传时用户填写，中文）。注意：它不是平台展示名 ——
    # 展示名由 constants.dataset_display_name_of(dataset) 统一给出（上传文件名去扩展名），
    # 本列只作为 file_path 缺失时的兜底。
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenario.id"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    fields_schema: Mapped[list] = mapped_column(JSONB, nullable=False)
    label_field: Mapped[str] = mapped_column(String(64), nullable=False)
    # 数据可见性分级：platform（平台）/ company（公司）/ personal（个人）。
    # 注意 default/server_default 都是 "platform"（最宽可见），这只是为了兼容
    # 20260814_000003 迁移给存量行回填的默认值；写入路径上 DatasetService.create /
    # upload_from_file 一定按上传者角色显式赋值（SCENARIO_USER 强制 personal），
    # 不允许依赖列默认值。绕过 Service 直接插 Dataset 会让个人数据变成全平台可见。
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="platform", server_default="platform"
    )
    uploader_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    uploaded_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # 数据集级 AI 解析产物（算法适配），与 model_version.ai_evaluation 同构：
    # 按数据集缓存最近一次解析结果，打开弹窗时直接读，不重复调用 AI。
    ai_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # ========== 迭代元数据（见 app/services/dataset_iteration.py） ==========
    # 本版本的产生方式；历史行由迁移回填（v1 → create，其余 → schema_change）。
    change_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # 血缘：本版从哪一版迭代而来；初次登记为 NULL。
    base_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dataset.id", ondelete="SET NULL"), nullable=True
    )
    # 是否破坏结构兼容（旧模型能否复用本版）。追加/修正样本为 False。
    is_breaking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    scenario: Mapped["Scenario"] = relationship(back_populates="datasets")
    uploader: Mapped["AppUser"] = relationship(back_populates="datasets")
    model_versions: Mapped[list["ModelVersion"]] = relationship(back_populates="dataset")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="dataset")
