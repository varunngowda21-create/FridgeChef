from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.services.freshness import (
    FreshnessStatus,
    calculate_freshness,
    get_freshness_for_item,
)


def test_freshness_boundary_conditions():
    today = date(2026, 10, 28)
    added_date = date(2026, 10, 20)

    # 1. days_left == 0 -> USE_FIRST
    res_0 = calculate_freshness(
        canonical_id="tomato",
        storage="FRIDGE",
        added_on=added_date,
        shelf_life_days=8,
        today=today,  # 8 days passed -> days_left = 0
    )
    assert res_0.days_left == 0
    assert res_0.status == FreshnessStatus.USE_FIRST
    assert res_0.days_left_display == "0 days"

    # 2. days_left == 1 -> USE_FIRST
    res_1 = calculate_freshness(
        canonical_id="tomato",
        storage="FRIDGE",
        added_on=added_date,
        shelf_life_days=9,
        today=today,  # 8 days passed -> days_left = 1
    )
    assert res_1.days_left == 1
    assert res_1.status == FreshnessStatus.USE_FIRST
    assert res_1.days_left_display == "1 day"

    # 3. days_left == 2 -> USE_SOON
    res_2 = calculate_freshness(
        canonical_id="tomato",
        storage="FRIDGE",
        added_on=added_date,
        shelf_life_days=10,
        today=today,  # 8 days passed -> days_left = 2
    )
    assert res_2.days_left == 2
    assert res_2.status == FreshnessStatus.USE_SOON
    assert res_2.days_left_display == "2 days"

    # 4. days_left == 3 -> USE_SOON
    res_3 = calculate_freshness(
        canonical_id="tomato",
        storage="FRIDGE",
        added_on=added_date,
        shelf_life_days=11,
        today=today,  # 8 days passed -> days_left = 3
    )
    assert res_3.days_left == 3
    assert res_3.status == FreshnessStatus.USE_SOON
    assert res_3.days_left_display == "3 days"

    # 5. days_left == 4 -> SAFE
    res_4 = calculate_freshness(
        canonical_id="tomato",
        storage="FRIDGE",
        added_on=added_date,
        shelf_life_days=12,
        today=today,  # 8 days passed -> days_left = 4
    )
    assert res_4.days_left == 4
    assert res_4.status == FreshnessStatus.SAFE
    assert res_4.days_left_display == "4 days"

    # 6. days_left > 365 -> "over a year"
    res_year = calculate_freshness(
        canonical_id="rice",
        storage="PANTRY",
        added_on=today,
        shelf_life_days=730,
        today=today,
    )
    assert res_year.days_left == 730
    assert res_year.status == FreshnessStatus.SAFE
    assert res_year.days_left_display == "over a year"


def test_opened_vs_unopened_shelf_life():
    today = date(2026, 10, 28)
    added_date = date(2026, 10, 20)
    opened_date = date(2026, 10, 26)

    # When opened_shelf_life_days is present: use opened_date and opened_shelf_life_days
    res_opened = calculate_freshness(
        canonical_id="milk",
        storage="FRIDGE",
        added_on=added_date,
        opened_on=opened_date,
        shelf_life_days=10,
        opened_shelf_life_days=3,
        today=today,  # 2 days passed since opened -> days_left = 3 - 2 = 1
    )
    assert res_opened.days_left == 1
    assert res_opened.status == FreshnessStatus.USE_FIRST
    assert res_opened.base_life == 3
    assert res_opened.expires_on == opened_date + timedelta(days=3)

    # When unopened: uses added_on and shelf_life_days
    res_unopened = calculate_freshness(
        canonical_id="milk",
        storage="FRIDGE",
        added_on=added_date,
        opened_on=None,
        shelf_life_days=10,
        opened_shelf_life_days=3,
        today=today,  # 8 days passed since added -> days_left = 10 - 8 = 2
    )
    assert res_unopened.days_left == 2
    assert res_unopened.status == FreshnessStatus.USE_SOON
    assert res_unopened.base_life == 10
    assert res_unopened.expires_on == added_date + timedelta(days=10)


def test_storage_not_applicable_rejection():
    # shelf_life_days is None or 0
    with pytest.raises(AppError) as exc_none:
        calculate_freshness(
            canonical_id="banana",
            storage="FREEZER",
            added_on=date.today(),
            shelf_life_days=None,
        )
    assert exc_none.value.code == "STORAGE_NOT_APPLICABLE"
    assert exc_none.value.status_code == 422

    with pytest.raises(AppError) as exc_zero:
        calculate_freshness(
            canonical_id="ice_cream",
            storage="PANTRY",
            added_on=date.today(),
            shelf_life_days=0,
        )
    assert exc_zero.value.code == "STORAGE_NOT_APPLICABLE"


def test_invalid_date_validation():
    today = date(2026, 10, 28)
    added_date = date(2026, 10, 25)

    # Opened date in the future
    with pytest.raises(AppError) as exc_future:
        calculate_freshness(
            canonical_id="tomato",
            storage="FRIDGE",
            added_on=added_date,
            opened_on=date(2026, 10, 29),
            shelf_life_days=7,
            today=today,
        )
    assert exc_future.value.code == "INVALID_DATE"

    # Opened date before added date
    with pytest.raises(AppError) as exc_before:
        calculate_freshness(
            canonical_id="tomato",
            storage="FRIDGE",
            added_on=added_date,
            opened_on=date(2026, 10, 20),
            shelf_life_days=7,
            today=today,
        )
    assert exc_before.value.code == "INVALID_DATE"


def test_database_backed_freshness_lookup(db_session: Session):
    # Test seeded item: tomato in FRIDGE (unopened shelf life = 7 days, opened = 3 days)
    today = date(2026, 10, 28)
    added_on = date(2026, 10, 25)

    freshness = get_freshness_for_item(
        db=db_session,
        ingredient_id="tomato",
        storage="FRIDGE",
        added_on=added_on,
        opened_on=None,
        today=today,
    )
    assert freshness.days_left == 4  # 7 - 3 = 4
    assert freshness.status == FreshnessStatus.SAFE
    assert freshness.base_life == 7

    # When opened yesterday: 3 - 1 = 2 days left
    freshness_opened = get_freshness_for_item(
        db=db_session,
        ingredient_id="tomato",
        storage="FRIDGE",
        added_on=added_on,
        opened_on=date(2026, 10, 27),
        today=today,
    )
    assert freshness_opened.days_left == 2
    assert freshness_opened.status == FreshnessStatus.USE_SOON
    assert freshness_opened.base_life == 3
