from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.catalogue import ShelfLife


class FreshnessStatus(str, Enum):
    USE_FIRST = "USE_FIRST"
    USE_SOON = "USE_SOON"
    SAFE = "SAFE"


@dataclass(frozen=True)
class FreshnessResult:
    days_left: int
    status: FreshnessStatus
    base_life: int
    expires_on: date
    days_left_display: str


def calculate_freshness(
    canonical_id: str,
    storage: str,
    added_on: date,
    opened_on: date | None = None,
    shelf_life_days: int | None = None,
    opened_shelf_life_days: int | None = None,
    today: date | None = None,
) -> FreshnessResult:
    """Deterministic calculation of remaining shelf-life per PRD Section 8.1."""
    if today is None:
        today = date.today()

    storage_upper = storage.strip().upper()

    # Rejection of 0 or null base shelf-life per PRD Section 8.1 & 11.4
    if shelf_life_days is None or shelf_life_days <= 0:
        raise AppError(
            code="STORAGE_NOT_APPLICABLE",
            message=(
                f"Storage location '{storage_upper}' is not applicable for ingredient '{canonical_id}'. "
                "Please select an applicable storage location."
            ),
            status_code=422,
        )

    # Date sanity validation
    if opened_on is not None:
        if opened_on > today:
            raise AppError(
                code="INVALID_DATE",
                message="Opened date cannot be in the future.",
                status_code=422,
            )
        if opened_on < added_on:
            raise AppError(
                code="INVALID_DATE",
                message="Opened date cannot be before added date.",
                status_code=422,
            )

    # If opened_date is set and opened_shelf_life_days is not null, use it as base_life
    if opened_on is not None and opened_shelf_life_days is not None and opened_shelf_life_days > 0:
        base_life = opened_shelf_life_days
        reference_date = opened_on
    else:
        base_life = shelf_life_days
        reference_date = opened_on if opened_on is not None else added_on

    age_days = (today - reference_date).days
    life_used = max(0, age_days)
    days_left = max(0, base_life - life_used)
    expires_on = reference_date + timedelta(days=base_life)

    # Classification per PRD Section 8.1:
    # - USE_FIRST: days_left <= 1
    # - USE_SOON: 2 <= days_left <= 3
    # - SAFE: days_left >= 4
    if days_left <= 1:
        status = FreshnessStatus.USE_FIRST
    elif days_left <= 3:
        status = FreshnessStatus.USE_SOON
    else:
        status = FreshnessStatus.SAFE

    if days_left > 365:
        days_left_display = "over a year"
    elif days_left == 1:
        days_left_display = "1 day"
    else:
        days_left_display = f"{days_left} days"

    return FreshnessResult(
        days_left=days_left,
        status=status,
        base_life=base_life,
        expires_on=expires_on,
        days_left_display=days_left_display,
    )


# Thread-safe in-memory cache for static catalogue shelf-life lookups
_SHELF_LIFE_CACHE: dict[tuple[str, str], tuple[int | None, int | None] | None] = {}


def get_freshness_for_item(
    db: Session,
    ingredient_id: str,
    storage: str,
    added_on: date,
    opened_on: date | None = None,
    today: date | None = None,
) -> FreshnessResult:
    """Retrieve shelf-life data from the catalogue and compute freshness."""
    storage_upper = storage.strip().upper()
    cache_key = (ingredient_id, storage_upper)

    if cache_key in _SHELF_LIFE_CACHE:
        entry = _SHELF_LIFE_CACHE[cache_key]
        if entry is None:
            shelf_days, opened_days = None, None
        else:
            shelf_days, opened_days = entry
    else:
        shelf_life_entry = (
            db.query(ShelfLife)
            .filter(
                ShelfLife.ingredient_id == ingredient_id,
                ShelfLife.storage == storage_upper,
            )
            .first()
        )
        if shelf_life_entry and shelf_life_entry.days is not None and shelf_life_entry.days > 0:
            shelf_days = shelf_life_entry.days
            opened_days = shelf_life_entry.opened_days
            _SHELF_LIFE_CACHE[cache_key] = (shelf_days, opened_days)
        else:
            shelf_days, opened_days = None, None
            _SHELF_LIFE_CACHE[cache_key] = None

    if shelf_days is None or shelf_days <= 0:
        raise AppError(
            code="STORAGE_NOT_APPLICABLE",
            message=(
                f"Storage location '{storage_upper}' is not applicable for ingredient '{ingredient_id}'. "
                "Please select an applicable storage location."
            ),
            status_code=422,
        )

    return calculate_freshness(
        canonical_id=ingredient_id,
        storage=storage_upper,
        added_on=added_on,
        opened_on=opened_on,
        shelf_life_days=shelf_days,
        opened_shelf_life_days=opened_days,
        today=today,
    )
