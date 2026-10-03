"""Helpers for opaque, server-side authentication sessions."""
import hashlib
import hmac
import os
import secrets

DEFAULT_SESSION_TTL_SECONDS = 8 * 60 * 60


def _pepper() -> bytes:
    value = os.environ.get("AUTH_SESSION_PEPPER", "").strip()
    if len(value) < 32:
        raise RuntimeError("AUTH_SESSION_PEPPER must be configured with at least 32 characters")
    return value.encode("utf-8")


def session_ttl() -> int:
    raw = os.environ.get("AUTH_SESSION_TTL_SECONDS", str(DEFAULT_SESSION_TTL_SECONDS))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        # 配置写错时给可读错误，而不是在登录路径上抛裸 ValueError
        raise RuntimeError("AUTH_SESSION_TTL_SECONDS must be an integer number of seconds") from None
    if value <= 0:
        raise RuntimeError("AUTH_SESSION_TTL_SECONDS must be positive")
    return value


def session_cookie_name() -> str:
    return os.environ.get("AUTH_SESSION_COOKIE_NAME", "bayes_session").strip() or "bayes_session"


def csrf_cookie_name() -> str:
    return os.environ.get("AUTH_CSRF_COOKIE_NAME", "bayes_csrf").strip() or "bayes_csrf"


def cookie_secure() -> bool:
    """Use Secure cookies by default; local HTTP development opts out explicitly."""
    return os.environ.get("AUTH_COOKIE_SECURE", "true").lower() == "true"


def cookie_samesite() -> str:
    value = os.environ.get("AUTH_COOKIE_SAMESITE", "lax").lower()
    return value if value in {"lax", "strict", "none"} else "lax"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def digest_token(token: str) -> str:
    return hmac.new(_pepper(), token.encode("utf-8"), hashlib.sha256).hexdigest()
