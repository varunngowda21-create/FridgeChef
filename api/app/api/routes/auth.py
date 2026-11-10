from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import verify_csrf_token
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import get_client_ip
from app.db.session import get_db
from app.schemas.auth import (
    RefreshTokenRequestBody,
    RefreshTokenResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.services.auth import (
    login_user,
    logout_user,
    refresh_user_tokens,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request_data: UserRegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Register a new user account with email, password, and display name."""
    return register_user(db=db, request=request_data, response=response)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    request: Request,
    request_data: UserLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email and password and issue access and refresh tokens."""
    client_ip = get_client_ip(request)
    return login_user(
        db=db,
        request=request_data,
        client_ip=client_ip,
        response=response,
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
)
def refresh(
    request: Request,
    response: Response,
    body: RefreshTokenRequestBody | None = None,
    db: Session = Depends(get_db),
) -> RefreshTokenResponse:
    """Rotate refresh token and issue a new access/refresh token pair."""
    settings = get_settings()

    if settings.AUTH_REFRESH_TRANSPORT == "cookie":
        verify_csrf_token(request)
        raw_refresh_token = request.cookies.get("refresh_token")
        if not raw_refresh_token:
            raise AppError(
                code="UNAUTHORIZED",
                message="Refresh token cookie is missing.",
                status_code=401,
            )
    else:
        if not body or not body.refresh_token:
            raise AppError(
                code="UNAUTHORIZED",
                message="Refresh token is required in request body.",
                status_code=401,
            )
        raw_refresh_token = body.refresh_token

    return refresh_user_tokens(
        db=db,
        raw_refresh_token=raw_refresh_token,
        response=response,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    response: Response,
    body: RefreshTokenRequestBody | None = None,
    db: Session = Depends(get_db),
) -> None:
    """Revoke the current refresh token and clear authentication cookies."""
    settings = get_settings()

    if settings.AUTH_REFRESH_TRANSPORT == "cookie":
        verify_csrf_token(request)
        raw_refresh_token = request.cookies.get("refresh_token")
    else:
        raw_refresh_token = body.refresh_token if body else None

    logout_user(
        db=db,
        raw_refresh_token=raw_refresh_token,
        response=response,
    )
