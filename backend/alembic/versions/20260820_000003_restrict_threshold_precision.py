"""restrict threshold precision to 2 decimal places"""
from alembic import context, op
import sqlalchemy as sa


revision = "20260820_000003"
down_revision = "20260820_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        return
    op.alter_column(
        "risk_threshold", "medium_threshold",
        existing_type=sa.Numeric(5, 4),
        type_=sa.Numeric(4, 2),
        existing_nullable=False,
        postgresql_using="ROUND(medium_threshold::numeric, 2)",
    )
    op.alter_column(
        "risk_threshold", "high_threshold",
        existing_type=sa.Numeric(5, 4),
        type_=sa.Numeric(4, 2),
        existing_nullable=False,
        postgresql_using="ROUND(high_threshold::numeric, 2)",
    )
    op.alter_column(
        "threshold_audit_log", "old_medium",
        existing_type=sa.Numeric(5, 4),
        type_=sa.Numeric(4, 2),
        existing_nullable=False,
        postgresql_using="ROUND(old_medium::numeric, 2)",
    )
    op.alter_column(
        "threshold_audit_log", "new_medium",
        existing_type=sa.Numeric(5, 4),
        type_=sa.Numeric(4, 2),
        existing_nullable=False,
        postgresql_using="ROUND(new_medium::numeric, 2)",
    )
    op.alter_column(
        "threshold_audit_log", "old_high",
        existing_type=sa.Numeric(5, 4),
        type_=sa.Numeric(4, 2),
        existing_nullable=False,
        postgresql_using="ROUND(old_high::numeric, 2)",
    )
    op.alter_column(
        "threshold_audit_log", "new_high",
        existing_type=sa.Numeric(5, 4),
        type_=sa.Numeric(4, 2),
        existing_nullable=False,
        postgresql_using="ROUND(new_high::numeric, 2)",
    )


def downgrade() -> None:
    op.alter_column(
        "risk_threshold", "medium_threshold",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(5, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "risk_threshold", "high_threshold",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(5, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "threshold_audit_log", "old_medium",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(5, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "threshold_audit_log", "new_medium",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(5, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "threshold_audit_log", "old_high",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(5, 4),
        existing_nullable=False,
    )
    op.alter_column(
        "threshold_audit_log", "new_high",
        existing_type=sa.Numeric(4, 2),
        type_=sa.Numeric(5, 4),
        existing_nullable=False,
    )