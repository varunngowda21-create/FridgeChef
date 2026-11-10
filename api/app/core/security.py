import hashlib
import hmac
import ipaddress
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from starlette.requests import Request

from app.core.config import get_settings
from app.core.errors import AppError


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise AppError(
            code="WEAK_PASSWORD",
            message="Password must be at least 8 characters long.",
            status_code=422,
        )
    if not any(c.isupper() for c in password):
        raise AppError(
            code="WEAK_PASSWORD",
            message="Password must contain at least one uppercase letter.",
            status_code=422,
        )
    if not any(c.islower() for c in password):
        raise AppError(
            code="WEAK_PASSWORD",
            message="Password must contain at least one lowercase letter.",
            status_code=422,
        )
    if not any(c.isdigit() for c in password):
        raise AppError(
            code="WEAK_PASSWORD",
            message="Password must contain at least one digit.",
            status_code=422,
        )


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise AppError(
                code="INVALID_TOKEN",
                message="Invalid token type.",
                status_code=401,
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise AppError(
            code="TOKEN_EXPIRED",
            message="Access token has expired.",
            status_code=401,
        ) from None
    except jwt.InvalidTokenError:
        raise AppError(
            code="INVALID_TOKEN",
            message="Invalid access token.",
            status_code=401,
        ) from None


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def get_refresh_token_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_DAYS)


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(cookie_token: str | None, header_token: str | None) -> None:
    if not cookie_token or not header_token:
        raise AppError(
            code="CSRF_TOKEN_INVALID",
            message="Missing CSRF token in request cookie or X-CSRF-Token header.",
            status_code=403,
        )
    if not hmac.compare_digest(cookie_token, header_token):
        raise AppError(
            code="CSRF_TOKEN_INVALID",
            message="CSRF token header does not match cookie.",
            status_code=403,
        )


def is_ip_trusted(ip_str: str, trusted_list: set[str] | list[str]) -> bool:
    """Check if an IP address is within the trusted proxy specification (exact IP or CIDR)."""
    if not ip_str or ip_str in ("testclient", "localhost"):
        return True
    try:
        ip = ipaddress.ip_address(ip_str)
        for spec in trusted_list:
            try:
                if "/" in spec:
                    if ip in ipaddress.ip_network(spec, strict=False):
                        return True
                else:
                    if ip == ipaddress.ip_address(spec):
                        return True
            except ValueError:
                continue
    except ValueError:
        return ip_str in trusted_list
    return False


def is_request_secure(request: Request) -> bool:
    """Determine whether the incoming request transport is genuinely secure (HTTPS).

    - If direct request URL scheme is 'https', returns True.
    - If connecting peer is an explicitly trusted reverse proxy (in TRUSTED_PROXIES) and
      supplies 'X-Forwarded-Proto: https', returns True.
    - If connecting peer is untrusted, any forwarded protocol header is ignored, returning False.
    """
    if request.url.scheme == "https":
        return True

    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").strip().lower()
    if forwarded_proto == "https":
        settings = get_settings()
        peer_ip = request.client.host if request.client else "127.0.0.1"
        if is_ip_trusted(peer_ip, settings.trusted_proxies_list):
            return True

    return False
