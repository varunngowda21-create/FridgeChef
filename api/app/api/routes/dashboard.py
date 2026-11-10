"""Dashboard API router per PRD Section 6.8, 11.10, and 12.3."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import Settings, get_settings
from app.db.models.auth import User
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import get_dashboard_data

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user dashboard",
    description="Returns freshness status counts, top recommendations, active meal plan summary, and month-to-date impact metrics.",
)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DashboardResponse:
    """Retrieve dashboard summary."""
    return await get_dashboard_data(
        db=db,
        user=current_user,
        settings=settings,
    )
