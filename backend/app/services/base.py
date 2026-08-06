"""Service 层公共基类与统一异常处理。

对应需求文档章节：6.5.2（权限矩阵）、5.2（访问控制要求）。

设计约定：
- 所有 Service 方法返回 app.schemas.common.ResponseModel（code=0 成功）。
- 业务异常统一抛出 ServiceError(code, message)，由 @service_call 装饰器转换为
  ResponseModel（400 校验失败 / 403 无权限 / 404 不存在）。
- SQLAlchemy 异常由 @service_call 统一捕获：回滚事务 + 记录日志 + 返回 code=500。
"""
import logging
from functools import wraps
from typing import Callable, Optional, TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.schemas.common import fail
from app.services.constants import ROLE_ADMIN, USER_STATUS_ENABLED

logger = logging.getLogger("app.services")

T = TypeVar("T")


class ServiceError(Exception):
    """业务异常，携带 HTTP-like code（400 / 403 / 404 等）。"""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def service_call(method: Callable[..., T]) -> Callable[..., T]:
    """统一异常处理装饰器：ServiceError → 对应 code；SQLAlchemyError/未知异常 → 500。"""

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except ServiceError as exc:
            # 任何异常路径都回滚，避免 flush 后未提交的变更残留在 session 中
            self.db.rollback()  # type: ignore[attr-defined]
            return fail(code=exc.code, message=exc.message)
        except SQLAlchemyError:
            self.db.rollback()  # type: ignore[attr-defined]
            logger.exception(
                "数据库操作失败: %s.%s", type(self).__name__, method.__name__
            )
            return fail(code=500, message="数据库操作失败")
        except Exception:
            logger.exception(
                "Service 未预期异常: %s.%s", type(self).__name__, method.__name__
            )
            return fail(code=500, message="服务器内部错误")

    return wrapper


class ServiceBase:
    """所有 Service 的公共基类。

    用法：
        class XxxService(ServiceBase):
            def __init__(self, db: Session):
                super().__init__(db)

    子类方法用 @service_call 装饰，即可获得统一异常转换。
    """

    logger = logging.getLogger("app.services")

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 权限检查（需求文档 6.5.2 权限矩阵 + 5.2 访问控制）
    # ------------------------------------------------------------------
    def require_login(self, user: Optional[object]) -> None:
        """必须登录且账号可用。"""
        if user is None or getattr(user, "status", None) != USER_STATUS_ENABLED:
            raise ServiceError(403, "无权限操作")

    def require_admin(self, user: Optional[object]) -> None:
        """仅管理员可操作。"""
        self.require_login(user)
        if getattr(user, "role", None) != ROLE_ADMIN:
            raise ServiceError(403, "无权限操作")

    def require_owner_or_admin(self, user: Optional[object], owner_id: int) -> None:
        """普通用户仅能操作本人资源（owner_id 对比）；管理员放行。"""
        self.require_login(user)
        if getattr(user, "role", None) == ROLE_ADMIN:
            return
        if getattr(user, "id", None) != owner_id:
            raise ServiceError(403, "无权限操作")

    # ------------------------------------------------------------------
    # 事务辅助
    # ------------------------------------------------------------------
    def commit(self) -> None:
        """提交事务；失败时回滚并抛出（由 @service_call 统一转换）。"""
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
