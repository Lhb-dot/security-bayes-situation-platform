"""migrate two-role model to three-role model

Revision ID: 20260814_000004
Revises: 20260814_000003
Create Date: 2026-08-14 00:00:04.000000

旧两级角色 → 三级角色：
- ADMIN  → SUPER_ADMIN（最外层管理员）
- USER   → SCENARIO_USER（场景用户）
并按用户名启发式给旧普通用户绑定场景（alice/bob/carol），保持演示数据可用。
"""
import sqlalchemy as sa
from alembic import op

revision = "20260814_000004"
down_revision = "20260814_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE app_user SET role = 'SUPER_ADMIN' WHERE role = 'ADMIN'")
    op.execute("UPDATE app_user SET role = 'SCENARIO_USER' WHERE role = 'USER'")

    # 旧普通用户按用户名绑定场景（演示账号），场景编码 → id 子查询
    bindings = {
        "alice": "network_security",
        "bob": "power_system",
        "carol": "geological_risk",
    }
    for username, code in bindings.items():
        op.execute(
            sa.text(
                "UPDATE app_user SET scenario_id = "
                "(SELECT id FROM scenario WHERE code = :code) "
                "WHERE username = :username AND scenario_id IS NULL"
            ).bindparams(code=code, username=username)
        )


def downgrade() -> None:
    op.execute("UPDATE app_user SET role = 'ADMIN' WHERE role = 'SUPER_ADMIN'")
    op.execute("UPDATE app_user SET role = 'USER' WHERE role = 'SCENARIO_USER'")
