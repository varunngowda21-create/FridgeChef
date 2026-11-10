from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.auth import User
from app.db.session import get_db
from app.schemas.user import (
    AccountDeleteRequest,
    AccountDeleteResponse,
    UserDataExport,
    UserPreferenceResponse,
    UserPreferenceUpdate,
    UserProfileResponse,
)
from app.services.user import (
    export_user_data,
    get_user_profile,
    schedule_account_deletion,
    update_user_preferences,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.get(
    "",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Retrieve authenticated user profile and preferences."""
    return get_user_profile(user=current_user)


@router.put(
    "/preferences",
    response_model=UserPreferenceResponse,
    status_code=status.HTTP_200_OK,
)
def update_preferences(
    update_data: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPreferenceResponse:
    """Update user household, dietary, spice, cuisine, and allergy preferences."""
    return update_user_preferences(
        db=db,
        user=current_user,
        update_data=update_data,
    )


@router.get(
    "/export",
    response_model=UserDataExport,
    status_code=status.HTTP_200_OK,
)
def export_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDataExport:
    """Export all user-scoped data in JSON format."""
    return export_user_data(db=db, user=current_user)


@router.delete(
    "",
    response_model=AccountDeleteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def delete_account(
    request_data: AccountDeleteRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountDeleteResponse:
    """Schedule user account deletion with 30-day grace period after password verification."""
    return schedule_account_deletion(
        db=db,
        user=current_user,
        password=request_data.password,
        response=response,
    )
