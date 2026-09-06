"""add opaque authentication sessions and enforce three-role bindings"""
from alembic import op
import sqlalchemy as sa

revision = "20260820_000001"
down_revision = "20260816_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE app_user SET role = 'SUPER_ADMIN' WHERE role = 'ADMIN'")
    op.execute("UPDATE app_user SET role = 'SCENARIO_USER' WHERE role = 'USER'")
    op.execute("UPDATE app_user SET scenario_id = NULL WHERE role = 'SUPER_ADMIN'")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM app_user
                WHERE role IN ('SCENARIO_ADMIN', 'SCENARIO_USER') AND scenario_id IS NULL
            ) THEN
                RAISE EXCEPTION 'scenario roles must have a bound scenario';
            END IF;
        END $$
    """)
    op.create_table(
        "auth_session",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_digest", sa.String(length=128), nullable=False),
        sa.Column("csrf_token_digest", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])
    op.create_index("ix_auth_session_expires_at", "auth_session", ["expires_at"])
    op.create_check_constraint(
        "ck_app_user_role",
        "app_user",
        "role IN ('SUPER_ADMIN', 'SCENARIO_ADMIN', 'SCENARIO_USER')",
    )
    op.create_check_constraint(
        "ck_app_user_role_scenario",
        "app_user",
        "(role = 'SUPER_ADMIN' AND scenario_id IS NULL) OR "
        "(role IN ('SCENARIO_ADMIN', 'SCENARIO_USER') AND scenario_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_user_role_scenario", "app_user", type_="check")
    op.drop_constraint("ck_app_user_role", "app_user", type_="check")
    op.drop_index("ix_auth_session_expires_at", table_name="auth_session")
    op.drop_index("ix_auth_session_user_id", table_name="auth_session")
    op.drop_table("auth_session")
