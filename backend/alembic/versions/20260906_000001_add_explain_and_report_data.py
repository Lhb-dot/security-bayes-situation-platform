"""add explain_data / report_data JSONB columns

Revision ID: 20260906_000001
Revises: 20260822_000007
Create Date: 2026-09-06 00:00:01.000000

态势感知报告落地：
- inference_record.explain_data：单条推理的算法可解释性信息
  （多视图预测 / 视图权重 / 特征加权条件概率），由 Java /predict 返回。
- report.report_data：结构化报告数据（统计 + 算法解释 + NL 分析），
  供前端渲染图表与溯源，不再只靠 content 文本。
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260906_000001"
down_revision = "20260822_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inference_record",
        sa.Column("explain_data", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "report",
        sa.Column("report_data", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("report", "report_data")
    op.drop_column("inference_record", "explain_data")
