"""add dataset iteration metadata and dataset_revision log

把「数据集迭代」提升为一等公民（见 app/services/dataset_iteration.py）：
dataset 增加三个迭代元数据列 —— change_type（本版是怎么产生的：create /
schema_change / append_rows 等）、base_version_id（血缘，本版从哪一版迭代而来）
、is_breaking（是否破坏结构兼容，旧模型能否复用本版）；同时新建
dataset_revision 表，每次迭代一条记录（原地更新也留痕），dataset
被物理删除时随 ON DELETE CASCADE 清理。

存量回填（迁移前只有「上传」与「修改字段」两条写入路径）：version = 1 回填
change_type='create'、is_breaking=false；version > 1 回填
change_type='schema_change'、is_breaking=true（旧路径只有改字段会升版本）；
base_version_id 指向同 logical_id 的上一版。
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261012_000001"
down_revision = "20261011_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dataset", sa.Column("change_type", sa.String(24), nullable=True))
    op.add_column(
        "dataset",
        sa.Column("base_version_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "dataset",
        sa.Column(
            "is_breaking", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_foreign_key(
        "fk_dataset_base_version_id",
        "dataset",
        "dataset",
        ["base_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "dataset_revision",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("logical_id", sa.String(64), nullable=False),
        sa.Column("dataset_id", sa.BigInteger(), nullable=False),
        sa.Column("change_type", sa.String(24), nullable=False),
        sa.Column(
            "is_breaking", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("result_dataset_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("summary", sa.String(255), nullable=True),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["result_dataset_id"], ["dataset.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dataset_revision_dataset_id", "dataset_revision", ["dataset_id"]
    )
    op.create_index(
        "ix_dataset_revision_logical_id", "dataset_revision", ["logical_id"]
    )

    # ---- 存量回填 ----
    op.execute(
        """
        UPDATE dataset
        SET change_type = CASE WHEN version = 1 THEN 'create' ELSE 'schema_change' END,
            is_breaking = (version > 1)
        """
    )
    op.execute(
        """
        UPDATE dataset d
        SET base_version_id = (
            SELECT p.id FROM dataset p
            WHERE p.logical_id = d.logical_id AND p.version < d.version
            ORDER BY p.version DESC LIMIT 1
        )
        WHERE d.version > 1
        """
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_revision_logical_id", table_name="dataset_revision")
    op.drop_index("ix_dataset_revision_dataset_id", table_name="dataset_revision")
    op.drop_table("dataset_revision")
    op.drop_constraint("fk_dataset_base_version_id", "dataset", type_="foreignkey")
    op.drop_column("dataset", "is_breaking")
    op.drop_column("dataset", "base_version_id")
    op.drop_column("dataset", "change_type")
