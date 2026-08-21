"""Login, session restoration, and logout endpoints."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_session, get_current_user
from app.api.utils import unwrap
from app.db import get_db
from app.models.app_user import AppUser
from app.models.auth_session import AuthSession
from app.schemas.auth import LoginRequest
from app.schemas.common import ResponseModel
from app.services.constants import USER_STATUS_ENABLED
from app.utils.auth import (
    cookie_samesite,
    cookie_secure,
    csrf_cookie_name,
    digest_token,
    new_token,
    session_cookie_name,
    session_ttl,
)
from app.utils.common import row_to_dict, verify_password

router = APIRouter(prefix="/auth", tags=["身份认证"])


def _payload(user: AppUser) -> dict:
    data = row_to_dict(user, exclude=("password_hash",))
    data["scenario_code"] = user.scenario.code if user.scenario is not None else None
    return data


def _set_cookies(response: Response, session_token: str, csrf_token: str, ttl: int) -> None:
    common = {
        "max_age": ttl,
        "expires": datetime.now(timezone.utc) + timedelta(seconds=ttl),
        "secure": cookie_secure(),
        "samesite": cookie_samesite(),
        "path": "/",
    }
    response.set_cookie(
        session_cookie_name(), session_token, httponly=True, **common
    )
    response.set_cookie(csrf_cookie_name(), csrf_token, httponly=False, **common)


@router.post("/login", response_model=ResponseModel, summary="账号登录")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(
        select(AppUser)
        .options(joinedload(AppUser.scenario))
        .where(AppUser.username == payload.username.strip())
    )
    if user is None or user.status != USER_STATUS_ENABLED or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    now = datetime.now(timezone.utc)
    ttl = session_ttl()
    session_token = new_token()
    csrf_token = new_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_digest=digest_token(session_token),
            csrf_token_digest=digest_token(csrf_token),
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
            last_seen_at=now,
        )
    )
    db.commit()
    _set_cookies(response, session_token, csrf_token, ttl)
    return {"code": 0, "data": {"user": _payload(user), "expires_in": ttl, "csrf_token": csrf_token}, "message": "success"}


@router.get("/me", response_model=ResponseModel, summary="获取当前登录账号")
def me(current_user: AppUser = Depends(get_current_user)):
    return {"code": 0, "data": {"user": _payload(current_user)}, "message": "success"}


@router.post("/logout", response_model=ResponseModel, summary="退出登录")
def logout(
    response: Response,
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    response.delete_cookie(session_cookie_name(), path="/")
    response.delete_cookie(csrf_cookie_name(), path="/")
    return {"code": 0, "data": None, "message": "success"}
