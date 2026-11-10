"""Recipe actions API router per PRD Section 11.7."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.auth import User
from app.schemas.recipes import RecipeCookedRequest, RecipeCookedResponse
from app.services.cooking import record_recipe_cooked

router = APIRouter(prefix="/recipes", tags=["Recipes"])


@router.post(
    "/{id}/cooked",
    response_model=RecipeCookedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record recipe cooked",
    description="Records a cooking event, decrements inventory by scaled quantities (floored at 0), and logs waste prevention.",
)
def cook_recipe(
    id: str,
    body: RecipeCookedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeCookedResponse:
    """Record recipe cooked and atomically decrement ingredients."""
    return record_recipe_cooked(
        db=db,
        user=current_user,
        recipe_id=id,
        request=body,
    )
