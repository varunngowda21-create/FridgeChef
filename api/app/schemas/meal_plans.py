"""Pydantic schemas for meal plans per PRD Section 6.6, 8.6, 10, and 11.8."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LockedSlotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(..., ge=1, le=7, description="Day of plan (1 to 7)")
    meal: str = Field(..., description="Meal type: 'LUNCH' or 'DINNER'")
    recipe_id: str = Field(..., min_length=1, description="Slug ID of recipe to lock")


class MealPlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = Field(None, description="Start date of 7-day plan (defaults to today)")
    locked_slots: list[LockedSlotInput] | None = Field(None, description="Optional locked slots to preserve")


class MealSlot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day: int
    date: date
    meal: str
    recipe_id: str
    recipe_title: str
    servings: int
    prioritised_ingredients: list[str] = Field(default_factory=list)
    waste_prevented_g: float = 0.0


class MealPlanResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    user_id: uuid.UUID
    start_date: date
    status: str
    low_variety: bool
    plan: dict[str, Any]
    created_at: datetime

