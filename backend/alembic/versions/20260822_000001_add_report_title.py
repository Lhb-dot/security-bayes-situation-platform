"""add report title for persisted report center records"""

import sqlalchemy as sa
from alembic import op


revision = "20260822_000001"
down_revision = "20260820_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "report",
        sa.Column("title", sa.String(128), nullable=False, server_default="未命名报告"),
    )
    op.alter_column("report", "title", server_default=None)


def downgrade() -> None:
    op.drop_column("report", "title")
