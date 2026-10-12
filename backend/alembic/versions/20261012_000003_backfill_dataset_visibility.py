"""backfill dataset visibility/uploader_role to the 2026-10 ownership model

数据级别（visibility）在 2026-10 定稿里**只由上传者角色决定、创建后不可变**：

    SUPER_ADMIN     → platform
    SCENARIO_ADMIN  → company
    SCENARIO_USER   → personal

存量行里有两类与之一致的缺口：

1. ``uploader_role`` 为空（20260814_000003 只加了列，没回填）；
2. ``visibility`` 是旧默认值 ``platform``，但上传者其实是场景管理员/场景用户
   —— 旧模型允许上传时自选可见性，历史数据可能标错级别（例如场景用户传的
   数据被标成 platform，在新模型下会泄漏给超管）。

因此按上传者当前角色重算这两列。上传者账号已删除（外键 SET NULL 之外不应发生）
的行保持原值不动。
"""

import sqlalchemy as sa
from alembic import op

revision = "20261012_000003"
down_revision = "20261012_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE dataset d
        SET uploader_role = u.role,
            visibility = CASE u.role
                WHEN 'SUPER_ADMIN' THEN 'platform'
                WHEN 'SCENARIO_ADMIN' THEN 'company'
                WHEN 'SCENARIO_USER' THEN 'personal'
                ELSE d.visibility
            END
        FROM app_user u
        WHERE u.id = d.uploaded_by
          AND u.role IN ('SUPER_ADMIN', 'SCENARIO_ADMIN', 'SCENARIO_USER')
        """
    )
    op.execute(
        """
        UPDATE dataset d
        SET uploader_role = u.role
        FROM app_user u
        WHERE u.id = d.uploaded_by
          AND d.uploader_role IS DISTINCT FROM u.role
        """
    )


def downgrade() -> None:
    # 回填是幂等的重算，没有可逆的信息（旧的自选 visibility 已丢失），不做动作。
    pass
