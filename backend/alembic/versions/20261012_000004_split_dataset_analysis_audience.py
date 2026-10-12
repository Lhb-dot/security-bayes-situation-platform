"""split dataset.ai_analysis into per-audience slots

数据集 AI 解析产物由单格 ``latest`` 改为按受众分格（management / user），
与研判解释、模型评价同一套机制：场景用户重新生成时只覆盖 ``user`` 格，
不会冲掉管理员看到的平台级解析。

存量数据只有 ``latest`` 一格，其内容由管理级账号生成，因此迁移为 ``management``。
"""

from alembic import op

revision = "20261012_000004"
down_revision = "20261012_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE dataset
        SET ai_analysis = (ai_analysis - 'latest')
            || jsonb_build_object('management', ai_analysis -> 'latest')
        WHERE ai_analysis ? 'latest'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE dataset
        SET ai_analysis = (ai_analysis - 'management')
            || jsonb_build_object('latest', ai_analysis -> 'management')
        WHERE ai_analysis ? 'management'
        """
    )
