from decimal import Decimal

from app.core.errors import AppError
from app.db.models.catalogue import Ingredient

BASE_UNITS = {"g", "ml", "piece"}

# Known volume / metric unit multipliers to base units
UNIT_MULTIPLIERS_TO_BASE: dict[str, tuple[str, Decimal]] = {
    # Weight -> g
    "g": ("g", Decimal("1")),
    "gram": ("g", Decimal("1")),
    "grams": ("g", Decimal("1")),
    "kg": ("g", Decimal("1000")),
    "kilogram": ("g", Decimal("1000")),
    "kilograms": ("g", Decimal("1000")),
    # Volume -> ml
    "ml": ("ml", Decimal("1")),
    "milliliter": ("ml", Decimal("1")),
    "milliliters": ("ml", Decimal("1")),
    "l": ("ml", Decimal("1000")),
    "liter": ("ml", Decimal("1000")),
    "liters": ("ml", Decimal("1000")),
    "tbsp": ("ml", Decimal("15")),
    "tablespoon": ("ml", Decimal("15")),
    "tsp": ("ml", Decimal("5")),
    "teaspoon": ("ml", Decimal("5")),
    "cup": ("ml", Decimal("240")),
    "cups": ("ml", Decimal("240")),
    # Piece / Packaged
    "piece": ("piece", Decimal("1")),
    "pieces": ("piece", Decimal("1")),
    "bunch": ("g", Decimal("200")),
    "packet": ("piece", Decimal("1")),
    "bottle": ("piece", Decimal("1")),
    "container": ("piece", Decimal("1")),
}


def normalize_unit(unit: str) -> str:
    """Normalize input unit string."""
    cleaned = unit.strip().lower()
    if cleaned in UNIT_MULTIPLIERS_TO_BASE:
        base_unit, _ = UNIT_MULTIPLIERS_TO_BASE[cleaned]
        return base_unit
    return cleaned


def convert_quantity_to_grams(
    ingredient: Ingredient,
    quantity: Decimal | float | int,
    unit: str,
) -> Decimal:
    """Convert a given quantity and unit of an ingredient into grams per PRD Section 8.5."""
    qty = Decimal(str(quantity))
    unit_lower = unit.strip().lower()

    if unit_lower in UNIT_MULTIPLIERS_TO_BASE:
        target_base, factor = UNIT_MULTIPLIERS_TO_BASE[unit_lower]
        if target_base == "g":
            return qty * factor
        elif target_base == "ml":
            # For culinary approximations in impact calculation, density 1g ≈ 1ml
            return qty * factor
        elif target_base == "piece":
            if ingredient.grams_per_piece is not None and ingredient.grams_per_piece > 0:
                return qty * factor * Decimal(str(ingredient.grams_per_piece))
            raise AppError(
                code="UNSUPPORTED_UNIT_CONVERSION",
                message=(
                    f"Cannot convert '{unit}' to grams for ingredient '{ingredient.id}' "
                    "because grams_per_piece is not defined."
                ),
                status_code=422,
            )

    raise AppError(
        code="UNSUPPORTED_UNIT_CONVERSION",
        message=f"Unit '{unit}' is not recognized or supported for conversion.",
        status_code=422,
    )


def calculate_estimated_cost(
    ingredient: Ingredient,
    quantity: Decimal | float | int,
    unit: str,
) -> Decimal:
    """Calculate estimated cost in INR based on price_inr_per_kg per PRD Section 8.5 & 8.8."""
    try:
        grams = convert_quantity_to_grams(ingredient, quantity, unit)
        price_per_gram = Decimal(str(ingredient.price_inr_per_kg)) / Decimal("1000")
        return round(grams * price_per_gram, 2)
    except AppError:
        # Fallback if grams_per_piece is missing: assume 100g per item
        qty = Decimal(str(quantity))
        price_per_gram = Decimal(str(ingredient.price_inr_per_kg)) / Decimal("1000")
        return round(qty * Decimal("100") * price_per_gram, 2)
