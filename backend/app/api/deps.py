"""FastAPI dependencies for authenticated users and role checks."""
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.app_user import AppUser
from app.models.auth_session import AuthSession
from app.services.constants import (
    ROLE_SCENARIO_ADMIN,
    ROLE_SUPER_ADMIN,
    USER_STATUS_ENABLED,
)
from app.utils.auth import csrf_cookie_name, digest_token, session_cookie_name


_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="未登录或账号不可用")


def get_current_session(
    request: Request,
    db: Session = Depends(get_db),
    csrf_header: str | None = Header(None, alias="X-CSRF-Token"),
) -> AuthSession:
    """Resolve a live server-side session from the HttpOnly cookie."""
    session_token = request.cookies.get(session_cookie_name())
    if not session_token:
        raise _unauthorized()

    session = db.scalar(
        select(AuthSession).where(AuthSession.token_digest == digest_token(session_token))
    )
    now = datetime.now(timezone.utc)
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
    ):
        raise _unauthorized()

    if request.method.upper() in _UNSAFE_METHODS:
        csrf_cookie = request.cookies.get(csrf_cookie_name())
        if (
            not csrf_cookie
            or not csrf_header
            or not _constant_time_digest_equal(
                session.csrf_token_digest, digest_token(csrf_cookie)
            )
            or not _constant_time_digest_equal(
                session.csrf_token_digest, digest_token(csrf_header)
            )
        ):
            raise HTTPException(status_code=403, detail="CSRF 校验失败")

    session.last_seen_at = now
    db.commit()
    return session


def _constant_time_digest_equal(expected: str, actual: str) -> bool:
    import hmac

    return hmac.compare_digest(expected, actual)


def get_current_user(
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> AppUser:
    """Resolve the enabled account belonging to the current session."""
    user = db.scalar(
        select(AppUser)
        .options(joinedload(AppUser.scenario))
        .where(AppUser.id == session.user_id)
    )
    if user is None or user.status != USER_STATUS_ENABLED:
        raise _unauthorized()
    return user


def require_admin(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    """Only the platform SUPER_ADMIN may use the endpoint."""
    if current_user.role != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="无权限操作")
    return current_user


def require_scenario_admin(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    """SUPER_ADMIN and the bound SCENARIO_ADMIN may use the endpoint."""
    if current_user.role not in (ROLE_SUPER_ADMIN, ROLE_SCENARIO_ADMIN):
        raise HTTPException(status_code=403, detail="无权限操作")
    return current_user


def require_bound_scenario(
    scenario_id: int,
    current_user: AppUser = Depends(get_current_user),
) -> AppUser:
    """Allow SUPER_ADMIN everywhere and other roles only in their bound scenario."""
    if current_user.role != ROLE_SUPER_ADMIN and current_user.scenario_id != scenario_id:
        raise HTTPException(status_code=403, detail="无权限操作")
    return current_user
