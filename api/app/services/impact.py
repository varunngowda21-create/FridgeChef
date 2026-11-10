"""Impact calculation service per PRD Section 6.8, 8.8, and FR-071."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models.catalogue import Ingredient
from app.db.models.inventory import WasteLog
from app.schemas.dashboard import MonthToDateImpact
from app.services.units import convert_quantity_to_grams

logger = logging.getLogger("fridgechef.impact")


def get_month_to_date_impact(
    db: Session,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> MonthToDateImpact:
    """Compute month-to-date food waste prevented, food wasted, and money saved in INR

    from waste_log records for the current calendar month in UTC.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    logs = (
        db.query(WasteLog)
        .filter(
            WasteLog.user_id == user_id,
            WasteLog.created_at >= start_of_month,
        )
        .all()
    )

    if not logs:
        return MonthToDateImpact(
            waste_prevented_kg=0.0,
            food_wasted_kg=0.0,
            money_saved_inr=0.0,
            is_estimate=True,
        )

    needed_ids = {entry.ingredient_id for entry in logs if entry.ingredient_id}
    ingredients = {
        ing.id: ing
        for ing in db.query(Ingredient).filter(Ingredient.id.in_(needed_ids)).all()
    }

    waste_prevented_grams = Decimal("0.0")
    wasted_grams = Decimal("0.0")
    money_saved = Decimal("0.0")

    for entry in logs:
        ing_model = ingredients.get(entry.ingredient_id)
        # Convert quantity to grams
        if ing_model:
            try:
                g = convert_quantity_to_grams(ing_model, entry.quantity, entry.unit)
            except Exception:
                g = Decimal(str(entry.quantity)) * Decimal("100.0")  # fallback estimate
        else:
            g = Decimal(str(entry.quantity)) * Decimal("100.0")

        if entry.action == "USED_BEFORE_EXPIRY":
            waste_prevented_grams += g
            money_saved += Decimal(str(entry.estimated_value_inr or "0.0"))
        elif entry.action == "WASTED":
            wasted_grams += g

    waste_prevented_kg = round(float(waste_prevented_grams / Decimal("1000.0")), 2)
    food_wasted_kg = round(float(wasted_grams / Decimal("1000.0")), 2)
    money_saved_inr = round(float(money_saved), 2)

    return MonthToDateImpact(
        waste_prevented_kg=waste_prevented_kg,
        food_wasted_kg=food_wasted_kg,
        money_saved_inr=money_saved_inr,
        is_estimate=True,
    )

