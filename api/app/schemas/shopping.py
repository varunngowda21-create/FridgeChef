"""Pydantic schemas for shopping lists per PRD Section 6.7, 8.7, 10, and 11.9."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecipeServingsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str = Field(..., min_length=1)
    servings: int = Field(2, ge=1, le=24)


class ManualShoppingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str = Field(..., min_length=1)
    qty: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)


class ShoppingListCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., description="'PLAN', 'RECIPES', or 'MANUAL'")
    plan_id: uuid.UUID | None = Field(None, description="Required when source is 'PLAN'")
    recipes: list[RecipeServingsItem] | None = Field(None, description="Required when source is 'RECIPES'")
    manual_items: list[ManualShoppingItem] | None = Field(None, description="Required when source is 'MANUAL'")


class ShoppingListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    canonical_id: str
    display_name: str
    category: str
    quantity: float
    unit: str
    est_cost_inr: float
    bought: bool = False


class ShoppingListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    user_id: uuid.UUID
    source: str
    items: list[ShoppingListItem] = Field(default_factory=list)
    total_est_cost_inr: float = 0.0
    created_at: datetime


class ShoppingItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bought: bool = Field(..., description="Whether item has been bought")
    add_to_inventory: bool = Field(False, description="Optionally auto-add bought quantity to inventory")

