from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.db.models.catalogue import Ingredient
from app.services.units import (
    calculate_estimated_cost,
    convert_quantity_to_grams,
    normalize_unit,
)


def test_unit_normalization():
    assert normalize_unit("kg") == "g"
    assert normalize_unit("grams") == "g"
    assert normalize_unit("l") == "ml"
    assert normalize_unit("liter") == "ml"
    assert normalize_unit("tbsp") == "ml"
    assert normalize_unit("cup") == "ml"
    assert normalize_unit("piece") == "piece"


def test_convert_quantity_to_grams_metric():
    ing = Ingredient(
        id="potato",
        display_name="Potato",
        category="Vegetables",
        default_unit="g",
        price_inr_per_kg=Decimal("40"),
        grams_per_piece=Decimal("150"),
    )

    # 500 grams -> 500 grams
    assert convert_quantity_to_grams(ing, 500, "g") == Decimal("500")

    # 2 kg -> 2000 grams
    assert convert_quantity_to_grams(ing, 2, "kg") == Decimal("2000")

    # 4 pieces -> 4 * 150 = 600 grams
    assert convert_quantity_to_grams(ing, 4, "piece") == Decimal("600")

    # 1 bunch of spinach -> 200g
    assert convert_quantity_to_grams(ing, 1, "bunch") == Decimal("200")


def test_convert_quantity_to_grams_missing_grams_per_piece():
    ing_no_weight = Ingredient(
        id="salt",
        display_name="Salt",
        category="Spices",
        default_unit="g",
        price_inr_per_kg=Decimal("25"),
        grams_per_piece=None,
    )
    with pytest.raises(AppError) as exc:
        convert_quantity_to_grams(ing_no_weight, 2, "piece")
    assert exc.value.code == "UNSUPPORTED_UNIT_CONVERSION"


def test_calculate_estimated_cost():
    ing = Ingredient(
        id="capsicum",
        display_name="Capsicum",
        category="Vegetables",
        default_unit="piece",
        price_inr_per_kg=Decimal("120"),  # 120 INR / kg
        grams_per_piece=Decimal("150"),   # 150g per piece
    )

    # 2 pieces = 300g -> 0.3 kg * 120 = 36 INR
    cost_piece = calculate_estimated_cost(ing, 2, "piece")
    assert cost_piece == Decimal("36.00")

    # 500g -> 0.5 kg * 120 = 60 INR
    cost_grams = calculate_estimated_cost(ing, 500, "g")
    assert cost_grams == Decimal("60.00")


def test_liquid_unit_conversions():
    ing = Ingredient(
        id="milk",
        display_name="Milk",
        category="Dairy",
        default_unit="ml",
        price_inr_per_kg=Decimal("60"),
    )
    # 500 ml -> 500 grams
    assert convert_quantity_to_grams(ing, 500, "ml") == Decimal("500")
    # 2 liters -> 2000 grams
    assert convert_quantity_to_grams(ing, 2, "l") == Decimal("2000")
    # 1 cup -> 240 grams
    assert convert_quantity_to_grams(ing, 1, "cup") == Decimal("240")
    # 2 tbsp -> 30 grams
    assert convert_quantity_to_grams(ing, 2, "tbsp") == Decimal("30")


def test_unrecognized_unit_rejection():
    ing = Ingredient(
        id="tomato",
        display_name="Tomato",
        category="Vegetables",
        default_unit="piece",
        price_inr_per_kg=Decimal("40"),
    )
    with pytest.raises(AppError) as exc:
        convert_quantity_to_grams(ing, 1, "alien_unit")
    assert exc.value.code == "UNSUPPORTED_UNIT_CONVERSION"


def test_calculate_estimated_cost_fallback_without_weight():
    ing_no_weight = Ingredient(
        id="exotic_spice",
        display_name="Exotic Spice",
        category="Spices",
        default_unit="piece",
        price_inr_per_kg=Decimal("500"),
        grams_per_piece=None,
    )
    # Fallback assumes 100g per piece: 2 * 100g = 200g -> 0.2 * 500 = 100 INR
    cost = calculate_estimated_cost(ing_no_weight, 2, "piece")
    assert cost == Decimal("100.00")

