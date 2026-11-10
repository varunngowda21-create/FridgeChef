"""Pydantic schemas for the dashboard endpoint per PRD Section 6.8, 11.10, FR-070, and FR-071."""

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendations import RecommendationItem


class FreshnessStatusCounts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    USE_FIRST: int = 0
    USE_SOON: int = 0
    SAFE: int = 0
    TOTAL: int = 0


class ActivePlanSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    start_date: date
    days_count: int = 7
    low_variety: bool = False
    today_meals: list[dict[str, Any]] = Field(default_factory=list)


class MonthToDateImpact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    waste_prevented_kg: float = 0.0
    food_wasted_kg: float = 0.0
    money_saved_inr: float = 0.0
    is_estimate: bool = True


class DashboardResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status_counts: FreshnessStatusCounts
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    active_plan: ActivePlanSummary | None = None
    impact: MonthToDateImpact

