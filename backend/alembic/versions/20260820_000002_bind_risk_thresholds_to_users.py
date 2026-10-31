"""把风险阈值和审计日志绑到目标用户"""
from alembic import context, op
import sqlalchemy as sa


revision = "20260820_000002"
down_revision = "20260820_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 存量场景级阈值直接归到最后改它的那个账号名下，值本身不动。
    # 基线迁移是按当时的 ORM 元数据建表的，所以这里要
    # 同时兼容「老库升级」和「全新安装、表里已经有新列」两种情况，
    # 不能假定列一定不存在。
    if context.is_offline_mode():
        # 全新安装生成的离线 SQL 已经带上当前 ORM 的完整结构，不必再补。
        return
    inspector = sa.inspect(op.get_bind())
    threshold_columns = {column["name"] for column in inspector.get_columns("risk_threshold")}
    if "user_id" not in threshold_columns:
        op.add_column(
            "risk_threshold",
            sa.Column("user_id", sa.BigInteger(), nullable=True),
        )
        op.execute(
            "UPDATE risk_threshold SET user_id = updated_by WHERE user_id IS NULL"
        )
        op.alter_column("risk_threshold", "user_id", nullable=False)

    threshold_pk = inspector.get_pk_constraint("risk_threshold").get("constrained_columns", [])
    if threshold_pk != ["user_id", "scenario_id"]:
        op.drop_constraint("risk_threshold_pkey", "risk_threshold", type_="primary")
        op.create_primary_key(
            "risk_threshold_pkey", "risk_threshold", ["user_id", "scenario_id"]
        )

    inspector = sa.inspect(op.get_bind())
    audit_columns = {column["name"] for column in inspector.get_columns("threshold_audit_log")}
    if "user_id" not in audit_columns:
        op.add_column(
            "threshold_audit_log",
            sa.Column("user_id", sa.BigInteger(), nullable=True),
        )
        op.execute(
            "UPDATE threshold_audit_log SET user_id = operator_id WHERE user_id IS NULL"
        )
        op.alter_column("threshold_audit_log", "user_id", nullable=False)

    inspector = sa.inspect(op.get_bind())
    if not _has_foreign_key(inspector, "risk_threshold", "user_id", "app_user"):
        op.create_foreign_key(
            "fk_risk_threshold_user",
            "risk_threshold",
            "app_user",
            ["user_id"],
            ["id"],
        )
    if not _has_foreign_key(inspector, "threshold_audit_log", "user_id", "app_user"):
        op.create_foreign_key(
            "fk_threshold_audit_log_user",
            "threshold_audit_log",
            "app_user",
            ["user_id"],
            ["id"],
        )


def downgrade() -> None:
    # 退回场景级表后一个场景只能挂一个账号，所以保留最早那一行，
    # 回滚结果才是确定的。
    inspector = sa.inspect(op.get_bind())
    _drop_foreign_key(inspector, "threshold_audit_log", "user_id", "app_user")
    _drop_foreign_key(inspector, "risk_threshold", "user_id", "app_user")
    op.drop_column("threshold_audit_log", "user_id")

    # 退回场景级主键后一个场景只能留一行，恢复旧主键之前先按场景保留最新那一行，
    # 否则恢复主键会直接撞唯一约束。
    op.execute(
        """
        DELETE FROM risk_threshold duplicate
        USING risk_threshold keep
        WHERE duplicate.scenario_id = keep.scenario_id
          AND (
              duplicate.updated_at > keep.updated_at
              OR (
                  duplicate.updated_at = keep.updated_at
                  AND duplicate.user_id > keep.user_id
              )
          )
        """
    )
    op.drop_constraint("risk_threshold_pkey", "risk_threshold", type_="primary")
    op.create_primary_key("risk_threshold_pkey", "risk_threshold", ["scenario_id"])
    op.drop_column("risk_threshold", "user_id")


def _has_foreign_key(inspector, table_name: str, column_name: str, referred_table: str) -> bool:
    return any(
        constraint.get("referred_table") == referred_table
        and constraint.get("constrained_columns") == [column_name]
        for constraint in inspector.get_foreign_keys(table_name)
    )


def _drop_foreign_key(inspector, table_name: str, column_name: str, referred_table: str) -> None:
    for constraint in inspector.get_foreign_keys(table_name):
        if (
            constraint.get("referred_table") == referred_table
            and constraint.get("constrained_columns") == [column_name]
        ):
            op.drop_constraint(constraint["name"], table_name, type_="foreignkey")
            return
