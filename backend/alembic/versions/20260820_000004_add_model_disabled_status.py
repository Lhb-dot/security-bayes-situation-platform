"""replace legacy model OFFLINE status with DISABLED"""
from alembic import op
import sqlalchemy as sa


revision = "20260820_000004"
down_revision = "20260820_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE model_version SET status = 'DISABLED' "
            "WHERE status = 'OFFLINE'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE model_version SET status = 'OFFLINE' "
            "WHERE status = 'DISABLED'"
        )
    )
