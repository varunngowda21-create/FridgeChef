import os
from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlalchemy.orm import Session

from app.api.deps import clear_auth_cookies
from app.core.errors import AppError
from app.core.security import verify_password
from app.db.models.analytics import RecommendationCache
from app.db.models.auth import RefreshToken, User, UserPreference
from app.db.models.inventory import CookingEvent, InventoryItem, ScanSession, WasteLog
from app.db.models.planning import MealPlan, ShoppingList
from app.schemas.auth import UserBriefResponse
from app.schemas.user import (
    AccountDeleteResponse,
    UserDataExport,
    UserPreferenceResponse,
    UserPreferenceUpdate,
    UserProfileResponse,
)


def get_user_profile(user: User) -> UserProfileResponse:
    pref_response = (
        UserPreferenceResponse.model_validate(user.preferences)
        if user.preferences
        else None
    )
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        preferences=pref_response,
    )


def update_user_preferences(
    db: Session,
    user: User,
    update_data: UserPreferenceUpdate,
) -> UserPreferenceResponse:
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if not pref:
        pref = UserPreference(user_id=user.id, version=1)
        db.add(pref)

    pref.household_size = update_data.household_size
    pref.diet = update_data.diet
    pref.spice_level = update_data.spice_level
    pref.cuisines = update_data.cuisines
    pref.max_cooking_time = update_data.max_cooking_time
    pref.allergies = update_data.allergies
    pref.avoided_ingredients = update_data.avoided_ingredients
    pref.version = pref.version + 1

    # Invalidate recommendation cache for this user (PRD FR-046)
    db.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).delete()

    db.commit()
    db.refresh(pref)
    return UserPreferenceResponse.model_validate(pref)


def export_user_data(db: Session, user: User) -> UserDataExport:
    # 1. Profile and Preferences
    user_brief = UserBriefResponse.model_validate(user)
    pref_response = (
        UserPreferenceResponse.model_validate(user.preferences)
        if user.preferences
        else None
    )

    # 2. Scoped User Data
    inventory_items = (
        db.query(InventoryItem)
        .filter(InventoryItem.user_id == user.id)
        .all()
    )
    scan_sessions = (
        db.query(ScanSession)
        .filter(ScanSession.user_id == user.id)
        .all()
    )
    waste_logs = (
        db.query(WasteLog)
        .filter(WasteLog.user_id == user.id)
        .all()
    )
    meal_plans = (
        db.query(MealPlan)
        .filter(MealPlan.user_id == user.id)
        .all()
    )
    shopping_lists = (
        db.query(ShoppingList)
        .filter(ShoppingList.user_id == user.id)
        .all()
    )
    cooking_events = (
        db.query(CookingEvent)
        .filter(CookingEvent.user_id == user.id)
        .all()
    )

    def serialize_model(item: object) -> dict:
        return {
            col.name: getattr(item, col.name).isoformat()
            if isinstance(getattr(item, col.name), datetime)
            else (str(getattr(item, col.name)) if hasattr(getattr(item, col.name), "hex") else getattr(item, col.name))
            for col in item.__table__.columns  # type: ignore[attr-defined]
        }

    return UserDataExport(
        user=user_brief,
        preferences=pref_response,
        inventory_items=[serialize_model(i) for i in inventory_items],
        scan_sessions=[serialize_model(s) for s in scan_sessions],
        waste_log=[serialize_model(w) for w in waste_logs],
        meal_plans=[serialize_model(m) for m in meal_plans],
        shopping_lists=[serialize_model(sl) for sl in shopping_lists],
        cooking_events=[serialize_model(c) for c in cooking_events],
        exported_at=datetime.now(timezone.utc),
    )


def schedule_account_deletion(
    db: Session,
    user: User,
    password: str,
    response: Response,
) -> AccountDeleteResponse:
    if not verify_password(password, user.password_hash):
        raise AppError(
            code="INVALID_CREDENTIALS",
            message="Invalid password.",
            status_code=401,
        )

    now = datetime.now(timezone.utc)
    user.deleted_at = now

    # Revoke all active refresh tokens for the user
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": now})

    # Purge immediate assets: images for user's scan sessions (PRD NFR-030)
    scan_sessions = (
        db.query(ScanSession).filter(ScanSession.user_id == user.id).all()
    )
    for session in scan_sessions:
        if session.image_path and os.path.exists(session.image_path):
            try:
                os.remove(session.image_path)
            except OSError:
                pass
            session.image_path = None

    db.commit()
    clear_auth_cookies(response)

    scheduled_at = now + timedelta(days=30)
    return AccountDeleteResponse(
        message="Account deletion scheduled. All personal data will be purged in 30 days.",
        scheduled_deletion_at=scheduled_at,
        status="SCHEDULED",
    )
