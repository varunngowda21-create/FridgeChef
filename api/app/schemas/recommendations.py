"""Pydantic schemas for recipe recommendations per PRD Section 11.6 and FR-044."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UsesExpiringItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    status: str  # "USE_FIRST" or "USE_SOON"
    days_left: int


class MissingIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    qty: float
    unit: str
    est_cost_inr: float


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    title: str
    cuisine: str
    cooking_time_minutes: int
    servings: int
    match_percent: int
    source: str = "CURATED"
    uses_expiring: list[UsesExpiringItem] = Field(default_factory=list)
    missing: list[MissingIngredient] = Field(default_factory=list)
    missing_cost_inr: float = 0.0
    reason: str


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degraded: bool = False
    generated_at: datetime
    cache: str  # "HIT" or "MISS"
    items: list[RecommendationItem] = Field(default_factory=list)
