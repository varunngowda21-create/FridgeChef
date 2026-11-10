"""Recommendations API router per PRD Section 11.6."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.auth import User
from app.schemas.recommendations import RecommendationResponse
from app.services.recommendations import get_recommendations

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get(
    "",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get top recipe recommendations",
    description="Returns top recipes ranked by deterministic waste-prevention score, cached for 30m.",
)
async def list_recommendations(
    limit: int = Query(5, ge=1, le=20, description="Max recipes to return (default 5)"),
    servings: int | None = Query(None, ge=1, le=24, description="Target servings to scale quantities"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """Retrieve ranked recipe recommendations using deterministic scoring and caching."""
    return await get_recommendations(
        db=db,
        user=current_user,
        limit=limit,
        servings=servings,
    )

