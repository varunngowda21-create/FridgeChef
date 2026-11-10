import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class InventoryItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str = Field(min_length=1, description="Canonical ingredient ID")
    quantity: Decimal = Field(gt=0, description="Quantity of ingredient (must be > 0)")
    unit: str = Field(min_length=1, description="Measurement unit (e.g. piece, g, ml, etc.)")
    storage: str = Field(min_length=1, description="Storage location (FRIDGE, FREEZER, PANTRY, COUNTER)")
    opened_on: date | None = Field(default=None, description="Date opened, if opened")
    added_on: date | None = Field(default=None, description="Date added to inventory (defaults to today)")
    display_name: str | None = Field(default=None, description="Optional custom display name")

    @field_validator("canonical_id")
    @classmethod
    def clean_canonical_id(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("canonical_id must not be empty.")
        return cleaned

    @field_validator("storage")
    @classmethod
    def clean_storage(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("storage must not be empty.")
        return cleaned


class InventoryItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Decimal | None = Field(default=None, gt=0)
    storage: str | None = None
    opened_on: date | None = None
    added_on: date | None = None
    display_name: str | None = None

    @field_validator("storage")
    @classmethod
    def clean_storage(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip().upper()
            if not cleaned:
                raise ValueError("storage must not be empty.")
            return cleaned
        return None


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    ingredient_id: str | None
    display_name: str
    quantity: Decimal
    unit: str
    storage: str
    added_on: date
    opened_on: date | None
    shelf_life_days_estimate: int | None
    expires_on: date | None
    days_left: int
    days_left_display: str
    status: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("quantity", when_used="json")
    def serialize_quantity(self, v: Decimal) -> float:
        return float(v)


class InventoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InventoryItemResponse]
    next_cursor: str | None = None


class InventoryUseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Decimal = Field(gt=0, description="Quantity used (must be > 0)")


class InventoryUseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: InventoryItemResponse
    action_logged: str | None = None
    quantity_used: Decimal
    is_archived: bool

    @field_serializer("quantity_used", when_used="json")
    def serialize_quantity_used(self, v: Decimal) -> float:
        return float(v)


class InventoryWasteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Decimal | None = Field(default=None, gt=0, description="Quantity wasted (defaults to remaining quantity)")


class InventoryWasteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: InventoryItemResponse
    action_logged: str = "WASTED"
    quantity_wasted: Decimal
    estimated_value_inr: Decimal
    is_archived: bool

    @field_serializer("quantity_wasted", "estimated_value_inr", when_used="json")
    def serialize_decimals(self, v: Decimal) -> float:
        return float(v)
