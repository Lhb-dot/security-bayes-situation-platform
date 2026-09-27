"""Server-side authenticated sessions.

安全不变量（改动本表前请先读这里）：
- **不落明文令牌**：cookie 里的 session/csrf 令牌只在客户端存在，库里只存
  ``digest_token()`` 的 HMAC-SHA256 摘要（app/utils/auth.py，带 AUTH_SESSION_PEPPER）。
- **过期与撤销都有列**：``expires_at`` 在 app/api/deps.get_current_session 里强制校验，
  ``revoked_at`` 非空即失效（登出置位；改密时由 user_service.update_password 批量置位）。
- ``token_digest`` 上的 UNIQUE 约束自带唯一索引，按令牌查会话是索引点查，不会全表扫。
- ``ix_auth_session_expires_at`` 目前无查询使用，是为「清理过期会话」预留的索引。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AuthSession(Base):
    __tablename__ = "auth_session"
    __table_args__ = (
        Index("ix_auth_session_user_id", "user_id"),
        Index("ix_auth_session_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    token_digest: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    csrf_token_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 目前全项目没有任何调用点使用 session.user（鉴权只读 user_id）。
    # 保留是为了让 AuthSession 可独立用于审计/后台任务；如需删除请走提案。
    user = relationship("AppUser")
