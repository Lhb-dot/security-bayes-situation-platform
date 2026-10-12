"""数据集迭代策略（DatasetRevision）。

把「迭代类型」与「是否新建版本快照」解耦：

- **迭代**：每一次数据/结构/元数据变更都算一次迭代，落一条 dataset_revision 记录；
- **版本**：迭代的产物，由本模块的纯函数 ``resolve_iteration_policy`` 按
  ``change_type x 是否已被模型引用`` 决定 —— 原地更新当前版本行，或新开一个版本快照。

这样「修改字段」与「追加数据条数」不需要两套逻辑：操作类型只是入参之一，
真正决定分叉的是「是否破坏结构兼容」与「是否已被引用」。

设计原则：
1. 破坏结构兼容的迭代（字段/标签变更）**必须**留版本快照，即使当前未被引用，
   否则旧模型/训练记录会指向一个字段已变的文件。
2. 兼容迭代（追加/修正样本）在**已被引用**时必须新开版本，冻结旧文件供历史追溯；
   未被引用时原地更新即可，避免版本号与文件副本无谓膨胀。
3. 纯元数据迭代（改名/可见性）不触碰数据文件，永远原地更新。
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 迭代类型（change_type）
# ---------------------------------------------------------------------------
CHANGE_TYPE_CREATE = "create"                # 初次登记（v1）
CHANGE_TYPE_APPEND_ROWS = "append_rows"      # 追加样本（兼容）
CHANGE_TYPE_UPDATE_ROWS = "update_rows"      # 修正 / 删除样本（兼容）
CHANGE_TYPE_RESAMPLE = "resample"            # 重采样 / 清洗（兼容）
CHANGE_TYPE_REPLACE_FILE = "replace_file"    # 整包替换文件（结构相同则兼容）
CHANGE_TYPE_SCHEMA_CHANGE = "schema_change"  # 字段结构变更（破坏兼容）
CHANGE_TYPE_LABEL_CHANGE = "label_change"    # 标签字段变更（破坏兼容）
CHANGE_TYPE_METADATA = "metadata"            # 名称等元数据（不碰文件；可见性由上传者角色固定，不可改）

#: 全部合法迭代类型
CHANGE_TYPES = (
    CHANGE_TYPE_CREATE,
    CHANGE_TYPE_APPEND_ROWS,
    CHANGE_TYPE_UPDATE_ROWS,
    CHANGE_TYPE_RESAMPLE,
    CHANGE_TYPE_REPLACE_FILE,
    CHANGE_TYPE_SCHEMA_CHANGE,
    CHANGE_TYPE_LABEL_CHANGE,
    CHANGE_TYPE_METADATA,
)

#: 会改变字段结构、导致旧模型不可直接复用的迭代类型
BREAKING_CHANGE_TYPES = frozenset(
    {CHANGE_TYPE_SCHEMA_CHANGE, CHANGE_TYPE_LABEL_CHANGE}
)

#: 迭代类型的中文展示名（后端日志 / 前端标签共用口径）
CHANGE_TYPE_LABELS = {
    CHANGE_TYPE_CREATE: "初次登记",
    CHANGE_TYPE_APPEND_ROWS: "追加样本",
    CHANGE_TYPE_UPDATE_ROWS: "修正样本",
    CHANGE_TYPE_RESAMPLE: "重采样",
    CHANGE_TYPE_REPLACE_FILE: "替换文件",
    CHANGE_TYPE_SCHEMA_CHANGE: "字段变更",
    CHANGE_TYPE_LABEL_CHANGE: "标签变更",
    CHANGE_TYPE_METADATA: "元数据变更",
}

#: 产物模式
MODE_IN_PLACE = "in_place"        # 原地更新当前版本行（不新增版本）
MODE_NEW_VERSION = "new_version"  # 新开一个版本快照


@dataclass(frozen=True)
class IterationDecision:
    """一次迭代的产物决策。"""

    mode: str          # MODE_IN_PLACE / MODE_NEW_VERSION
    is_breaking: bool  # 是否破坏结构兼容（下游据此判断旧模型能否复用）
    reason: str        # 决策原因，写入 revision 便于追溯


def change_type_label(change_type: str) -> str:
    """取迭代类型的中文展示名；未知类型原样返回。"""
    return CHANGE_TYPE_LABELS.get(change_type, change_type)


def resolve_iteration_policy(
    change_type: str,
    *,
    referenced: bool,
    schema_unchanged: bool = False,
) -> IterationDecision:
    """决定一次迭代的产物：原地更新还是新建版本。

    Args:
        change_type: 迭代类型，取值见 ``CHANGE_TYPES``。
        referenced: 目标数据集版本是否已被模型版本引用。
        schema_unchanged: 仅对 ``replace_file`` 有意义 —— 替换后字段结构是否与
            当前版本完全一致。一致则视为兼容迭代，否则按破坏性处理。

    Raises:
        ValueError: change_type 不在 ``CHANGE_TYPES`` 内。
    """
    if change_type not in CHANGE_TYPES:
        raise ValueError(f"未知的数据集迭代类型: {change_type}")

    if change_type == CHANGE_TYPE_METADATA:
        return IterationDecision(
            MODE_IN_PLACE, False, "元数据变更不触碰数据文件，原地更新即可"
        )

    if change_type == CHANGE_TYPE_CREATE:
        return IterationDecision(
            MODE_NEW_VERSION, False, "初次登记，直接生成首个版本"
        )

    if change_type == CHANGE_TYPE_REPLACE_FILE:
        # 整包替换：字段结构没变就是兼容迭代，变了按破坏性处理
        is_breaking = not schema_unchanged
    else:
        is_breaking = change_type in BREAKING_CHANGE_TYPES

    if is_breaking:
        # 结构变了：即使未被引用也留版本，避免旧模型/训练记录指向已变的字段
        return IterationDecision(
            MODE_NEW_VERSION, True, "字段结构变更，必须保留可追溯的版本快照"
        )

    if referenced:
        return IterationDecision(
            MODE_NEW_VERSION, False, "数据集已被模型引用，旧版本文件必须冻结"
        )

    return IterationDecision(
        MODE_IN_PLACE, False, "兼容变更且未被引用，原地更新当前版本"
    )
