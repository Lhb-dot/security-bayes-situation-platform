"""数据集迭代表 dataset_revision —— 每一次迭代一条记录。

设计动机见 app/services/dataset_iteration.py：**迭代**与**版本**是两件事。
- 每次数据/结构/元数据变更都算一次迭代，无论最终是原地更新还是新开版本，都落一条本表记录；
- 版本快照（dataset 行）只在策略判定需要时才新增。

于是「追加数据条数」这类兼容迭代在未被引用时可以原地更新，不涨版本号，但依然可追溯；
被引用后自动改为新建版本，冻结旧文件。前端「版本管理」看版本，审计看本表。

本表是纯日志，不参与业务计算；dataset 被物理删除时随库级 ON DELETE CASCADE 一并清理。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DatasetRevision(Base):
    __tablename__ = "dataset_revision"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    logical_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 被迭代的目标版本行（原地更新时就是它本身；新建版本时是迭代前的版本）
    dataset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False
    )
    # 迭代类型，取值见 dataset_iteration.CHANGE_TYPES
    change_type: Mapped[str] = mapped_column(String(24), nullable=False)
    # 是否破坏结构兼容
    is_breaking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # 产物模式：in_place（原地更新）/ new_version（新开版本快照）
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    # 新建版本时指向新版本行；原地更新为 NULL
    result_dataset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dataset.id", ondelete="SET NULL"), nullable=True
    )
    # 决策原因（来自 resolve_iteration_policy）+ 人类可读摘要
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 迭代细节（如追加条数、字段 diff），结构随类型变化，读取方按需解析
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
