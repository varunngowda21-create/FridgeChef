"""Schemas for scan session and verification endpoints."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.inventory import InventoryItemResponse


class ScanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID
    name: str
    canonical_id: str | None = None
    quantity: float | None = None
    unit: str = "unknown"
    storage_guess: str = "UNKNOWN"
    confidence: str = "MEDIUM"
    needs_review: bool = False
    visible_note: str | None = None


class ScanSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: uuid.UUID
    status: str = "PENDING_VERIFY"
    expires_at: datetime
    image_quality: str = "GOOD"
    image_quality_note: str | None = None
    candidates: list[ScanCandidate] = Field(default_factory=list)


class ScanConfirmItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID | None = None
    canonical_id: str | None = None
    name: str = Field(min_length=1)
    quantity: Decimal = Field(ge=0, description="Quantity to add (must be >= 0)")
    unit: str = Field(min_length=1)
    storage: str = Field(min_length=1)
    opened_on: date | None = None

    @field_validator("storage")
    @classmethod
    def clean_storage(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("storage must not be empty.")
        return cleaned


class ScanConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanConfirmItem]


class ScanConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: list[InventoryItemResponse]
    skipped: list[str] = Field(default_factory=list)
