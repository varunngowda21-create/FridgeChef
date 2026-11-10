"""Pydantic schemas for recipe actions per PRD Section 11.7."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecipeCookedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servings: int | None = Field(default=None, ge=1, le=24, description="Servings cooked (defaults to household size)")
    rating: int | None = Field(default=None, ge=1, le=5, description="Optional rating 1 to 5")


class RecipeCookedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    recipe_id: str
    servings: int
    rating: int | None = None
    decremented_items_count: int
    waste_prevented_logged: bool
    created_at: datetime
