import uuid

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decode_access_token, verify_csrf
from app.db.models.auth import User
from app.db.session import get_db

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise AppError(
            code="UNAUTHORIZED",
            message="Authentication credentials were not provided.",
            status_code=401,
        )

    payload = decode_access_token(credentials.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AppError(
            code="UNAUTHORIZED",
            message="Invalid token payload.",
            status_code=401,
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise AppError(
            code="UNAUTHORIZED",
            message="Invalid token user ID.",
            status_code=401,
        ) from None

    user = (
        db.query(User)
        .options(joinedload(User.preferences))
        .filter(User.id == user_id, User.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise AppError(
            code="UNAUTHORIZED",
            message="User account not found or has been deactivated.",
            status_code=401,
        )

    return user


def verify_csrf_token(request: Request) -> None:
    settings = get_settings()
    if settings.AUTH_REFRESH_TRANSPORT != "cookie":
        return

    csrf_cookie = request.cookies.get("csrf_token")
    csrf_header = request.headers.get("X-CSRF-Token")
    verify_csrf(csrf_cookie, csrf_header)


def set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    settings = get_settings()
    if settings.AUTH_REFRESH_TRANSPORT != "cookie":
        return

    is_production = settings.APP_ENV == "production"
    max_age = settings.REFRESH_TOKEN_DAYS * 86400

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=max_age,
        expires=max_age,
        path="/api/v1/auth",
        httponly=True,
        secure=is_production,
        samesite="lax",
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        max_age=max_age,
        expires=max_age,
        path="/",
        httponly=False,
        secure=is_production,
        samesite="lax",
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    if settings.AUTH_REFRESH_TRANSPORT != "cookie":
        return

    is_production = settings.APP_ENV == "production"

    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        httponly=True,
        secure=is_production,
        samesite="lax",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        httponly=False,
        secure=is_production,
        samesite="lax",
    )
