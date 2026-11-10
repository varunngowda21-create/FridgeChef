"""Meal plans API router per PRD Section 6.6, 8.6, 10, and 11.8."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.auth import User
from app.schemas.meal_plans import MealPlanCreateRequest, MealPlanResponse
from app.services.planner import (
    archive_meal_plan,
    generate_weekly_meal_plan,
    get_active_meal_plan,
    get_meal_plan_by_id,
    regenerate_plan_slot,
)

router = APIRouter(prefix="/meal-plans", tags=["Meal Plans"])


@router.post(
    "",
    response_model=MealPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create 7-day meal plan",
    description="Generates a deterministic 7-day, 14-slot weekly meal plan using greedy lookahead inventory simulation.",
)
def create_meal_plan(
    body: MealPlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealPlanResponse:
    """Generate weekly meal plan."""
    return generate_weekly_meal_plan(
        db=db,
        user=current_user,
        start_date=body.start_date,
        locked_slots=body.locked_slots,
    )


@router.get(
    "/active",
    response_model=MealPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active meal plan",
    description="Retrieves the current active meal plan for the authenticated user, or returns 404.",
)
def get_active(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealPlanResponse:
    """Retrieve active meal plan."""
    return get_active_meal_plan(db=db, user=current_user)


@router.get(
    "/{id}",
    response_model=MealPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meal plan by ID",
    description="Retrieves a specific meal plan by ID (scoped to owner).",
)
def get_by_id(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealPlanResponse:
    """Retrieve meal plan by ID."""
    return get_meal_plan_by_id(db=db, user=current_user, plan_id=id)


@router.post(
    "/{id}/slots/{day}/{meal}/regenerate",
    response_model=MealPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Regenerate single meal slot",
    description="Regenerates a single meal plan slot while preserving the other 13 slots.",
)
def regenerate_slot(
    id: uuid.UUID,
    day: int,
    meal: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealPlanResponse:
    """Regenerate single slot in meal plan."""
    return regenerate_plan_slot(
        db=db,
        user=current_user,
        plan_id=id,
        day=day,
        meal=meal,
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive meal plan",
    description="Archives a meal plan (soft deletion / status change).",
)
def delete_meal_plan(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Archive meal plan."""
    archive_meal_plan(db=db, user=current_user, plan_id=id)

