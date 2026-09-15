"""add model-level attributes and role-scoped AI evaluations"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260914_000002"
down_revision = "20260913_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_version",
        sa.Column("model_attributes", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "model_version",
        sa.Column("ai_evaluation", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_version", "ai_evaluation")
    op.drop_column("model_version", "model_attributes")
