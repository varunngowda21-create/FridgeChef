import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import UserBriefResponse


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    household_size: int
    diet: str
    spice_level: str
    cuisines: list[str]
    max_cooking_time: int
    allergies: list[str]
    avoided_ingredients: list[str]
    version: int


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime
    preferences: UserPreferenceResponse | None = None


ALLOWED_DIETS = {"VEGETARIAN", "EGGLESS", "NON_VEGETARIAN", "VEGAN"}
ALLOWED_SPICE_LEVELS = {"MILD", "MEDIUM", "HOT"}


class UserPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_size: int = Field(ge=1, le=10)
    diet: str
    spice_level: str
    cuisines: list[str] = Field(default_factory=list)
    max_cooking_time: int = Field(ge=5, le=180)
    allergies: list[str] = Field(default_factory=list)
    avoided_ingredients: list[str] = Field(default_factory=list)

    @field_validator("diet")
    @classmethod
    def validate_diet(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ALLOWED_DIETS:
            raise ValueError(f"diet must be one of {sorted(ALLOWED_DIETS)}, got '{v}'")
        return upper

    @field_validator("spice_level")
    @classmethod
    def validate_spice_level(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ALLOWED_SPICE_LEVELS:
            raise ValueError(f"spice_level must be one of {sorted(ALLOWED_SPICE_LEVELS)}, got '{v}'")
        return upper


class AccountDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1)


class AccountDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    scheduled_deletion_at: datetime
    status: str = "SCHEDULED"


class UserDataExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: UserBriefResponse
    preferences: UserPreferenceResponse | None
    inventory_items: list[dict[str, Any]]
    scan_sessions: list[dict[str, Any]]
    waste_log: list[dict[str, Any]]
    meal_plans: list[dict[str, Any]]
    shopping_lists: list[dict[str, Any]]
    cooking_events: list[dict[str, Any]]
    exported_at: datetime
