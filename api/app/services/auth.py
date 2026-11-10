from datetime import datetime, timezone

from fastapi import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import clear_auth_cookies, set_auth_cookies
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import login_rate_limiter
from app.core.security import (
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    get_refresh_token_expiry,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.models.auth import RefreshToken, User, UserPreference
from app.schemas.auth import (
    RefreshTokenResponse,
    TokenResponse,
    UserBriefResponse,
    UserLoginRequest,
    UserRegisterRequest,
)


def register_user(
    db: Session,
    request: UserRegisterRequest,
    response: Response,
) -> TokenResponse:
    settings = get_settings()

    # Check if email is already registered (case-insensitive)
    existing_user = (
        db.query(User).filter(func.lower(User.email) == request.email.lower()).first()
    )
    if existing_user:
        raise AppError(
            code="EMAIL_ALREADY_EXISTS",
            message="An account with this email already exists.",
            status_code=409,
        )

    # Create user
    user = User(
        email=request.email.lower(),
        password_hash=hash_password(request.password),
        display_name=request.display_name,
    )
    db.add(user)
    db.flush()

    # Create default user preferences
    default_preferences = UserPreference(
        user_id=user.id,
        household_size=2,
        diet="VEGETARIAN",
        spice_level="MEDIUM",
        cuisines=[],
        max_cooking_time=45,
        allergies=[],
        avoided_ingredients=[],
        version=1,
    )
    db.add(default_preferences)

    # Issue tokens
    access_token = create_access_token(user.id, user.email)
    raw_refresh_token = create_refresh_token()
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh_token),
        expires_at=get_refresh_token_expiry(),
        revoked_at=None,
    )
    db.add(token_record)
    db.commit()
    db.refresh(user)

    # Set cookies if cookie transport is active
    csrf_token = create_csrf_token()
    set_auth_cookies(response, raw_refresh_token, csrf_token)

    return TokenResponse(
        user=UserBriefResponse.model_validate(user),
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
        refresh_token=raw_refresh_token if settings.AUTH_REFRESH_TRANSPORT == "sessionstorage" else None,
    )


def login_user(
    db: Session,
    request: UserLoginRequest,
    client_ip: str,
    response: Response,
) -> TokenResponse:
    settings = get_settings()

    ip_key = f"ip:{client_ip}"
    email_key = f"email:{request.email.lower()}"

    # Rate limiting checks (PRD NFR-023: 10 attempts per 15 min per email and IP)
    login_rate_limiter.check_and_record(ip_key)
    login_rate_limiter.check_and_record(email_key)

    user = (
        db.query(User)
        .filter(func.lower(User.email) == request.email.lower(), User.deleted_at.is_(None))
        .first()
    )

    if not user or not verify_password(request.password, user.password_hash):
        # Generic error message to prevent account enumeration
        raise AppError(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
            status_code=401,
        )

    # Reset rate limit attempts on successful login
    login_rate_limiter.reset(ip_key)
    login_rate_limiter.reset(email_key)

    access_token = create_access_token(user.id, user.email)
    raw_refresh_token = create_refresh_token()
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh_token),
        expires_at=get_refresh_token_expiry(),
        revoked_at=None,
    )
    db.add(token_record)
    db.commit()

    csrf_token = create_csrf_token()
    set_auth_cookies(response, raw_refresh_token, csrf_token)

    return TokenResponse(
        user=UserBriefResponse.model_validate(user),
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
        refresh_token=raw_refresh_token if settings.AUTH_REFRESH_TRANSPORT == "sessionstorage" else None,
    )


def refresh_user_tokens(
    db: Session,
    raw_refresh_token: str | None,
    response: Response,
) -> RefreshTokenResponse:
    settings = get_settings()

    if not raw_refresh_token:
        raise AppError(
            code="UNAUTHORIZED",
            message="Refresh token is required.",
            status_code=401,
        )

    token_h = hash_token(raw_refresh_token)
    token_record = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_h).first()
    )

    if not token_record:
        clear_auth_cookies(response)
        raise AppError(
            code="UNAUTHORIZED",
            message="Invalid refresh token.",
            status_code=401,
        )

    now = datetime.now(timezone.utc)

    # Reuse detection: If the presented token has already been revoked,
    # it indicates potential token theft or replay attack.
    if token_record.revoked_at is not None:
        # Revoke all active refresh tokens for this user
        db.query(RefreshToken).filter(
            RefreshToken.user_id == token_record.user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})
        db.commit()
        clear_auth_cookies(response)
        raise AppError(
            code="TOKEN_REUSE_DETECTED",
            message="Refresh token reuse detected. All sessions have been revoked.",
            status_code=401,
        )

    # Expiration check
    if token_record.expires_at < now:
        token_record.revoked_at = now
        db.commit()
        clear_auth_cookies(response)
        raise AppError(
            code="REFRESH_TOKEN_EXPIRED",
            message="Refresh token has expired.",
            status_code=401,
        )

    user = (
        db.query(User)
        .filter(User.id == token_record.user_id, User.deleted_at.is_(None))
        .first()
    )
    if not user:
        token_record.revoked_at = now
        db.commit()
        clear_auth_cookies(response)
        raise AppError(
            code="UNAUTHORIZED",
            message="User account not found or has been deactivated.",
            status_code=401,
        )

    # Rotate refresh token: revoke current token and create new pair
    token_record.revoked_at = now
    new_raw_token = create_refresh_token()
    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw_token),
        expires_at=get_refresh_token_expiry(),
        revoked_at=None,
    )
    db.add(new_token_record)
    db.commit()

    new_access_token = create_access_token(user.id, user.email)
    new_csrf_token = create_csrf_token()
    set_auth_cookies(response, new_raw_token, new_csrf_token)

    return RefreshTokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
        refresh_token=new_raw_token if settings.AUTH_REFRESH_TRANSPORT == "sessionstorage" else None,
    )


def logout_user(
    db: Session,
    raw_refresh_token: str | None,
    response: Response,
) -> None:
    if raw_refresh_token:
        token_h = hash_token(raw_refresh_token)
        token_record = (
            db.query(RefreshToken).filter(RefreshToken.token_hash == token_h).first()
        )
        if token_record and token_record.revoked_at is None:
            token_record.revoked_at = datetime.now(timezone.utc)
            db.commit()

    clear_auth_cookies(response)
