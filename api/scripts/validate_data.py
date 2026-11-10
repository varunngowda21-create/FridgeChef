#!/usr/bin/env python3
"""
Data Validation Script for FridgeChef AI
Enforces referential integrity, schema constraints, and PRD rules
for ingredients.json, shelf_life.json, and recipes.json.
PRD References: Section 8.3, 8.4, 8.5, 14.5.
"""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

VALID_CATEGORIES = {
    "Vegetables",
    "Fruits",
    "Dairy and Eggs",
    "Proteins",
    "Grains and Pulses",
    "Spices",
    "Oils and Condiments",
    "Other",
}

VALID_DIETS = {"VEGETARIAN", "EGGLESS", "NON_VEGETARIAN", "VEGAN"}
VALID_SPICE_LEVELS = {"MILD", "MEDIUM", "HOT"}
VALID_STORAGES = {"FRIDGE", "FREEZER", "PANTRY", "COUNTER"}
VALID_UNITS = {"g", "ml", "piece", "bunch", "packet", "container", "bottle", "tbsp", "tsp", "cup"}


class ValidationError(Exception):
    pass


def find_data_dir() -> Path:
    # Look for data directory relative to script or cwd
    candidates = [
        Path(__file__).parent.parent / "data",
        Path.cwd() / "data",
        Path.cwd() / "api" / "data",
    ]
    for c in candidates:
        if c.is_dir() and (c / "ingredients.json").exists():
            return c
    raise ValidationError(f"Could not locate data directory with ingredients.json. Searched: {[str(c) for c in candidates]}")


def validate_ingredients(data_dir: Path) -> set[str]:
    filepath = data_dir / "ingredients.json"
    if not filepath.exists():
        raise ValidationError(f"Missing ingredients.json at {filepath}")

    with open(filepath, encoding="utf-8") as f:
        try:
            ingredients = json.load(f)
        except json.JSONDecodeError as e:
            raise ValidationError(f"ingredients.json is not valid JSON: {e}") from e

    if not isinstance(ingredients, list):
        raise ValidationError("ingredients.json must contain a JSON array.")

    if len(ingredients) < 200:
        raise ValidationError(f"PRD requires at least 200 canonical ingredients, found {len(ingredients)}.")

    ingredient_ids: set[str] = set()

    for idx, item in enumerate(ingredients):
        if not isinstance(item, dict):
            raise ValidationError(f"Ingredient at index {idx} must be an object.")

        # Required fields
        for field in ("id", "display_name", "category", "aliases", "default_unit", "price_inr_per_kg"):
            if field not in item:
                raise ValidationError(f"Ingredient {item.get('id', idx)} is missing required field '{field}'.")

        ing_id = item["id"]
        if not isinstance(ing_id, str) or not ing_id.strip():
            raise ValidationError(f"Invalid id for ingredient at index {idx}.")

        if ing_id in ingredient_ids:
            raise ValidationError(f"Duplicate ingredient id '{ing_id}' found at index {idx}.")
        ingredient_ids.add(ing_id)

        # Category check
        cat = item["category"]
        if cat not in VALID_CATEGORIES:
            raise ValidationError(f"Ingredient '{ing_id}' has invalid category '{cat}'. Valid categories: {VALID_CATEGORIES}")

        # Aliases check
        aliases = item["aliases"]
        if not isinstance(aliases, list) or len(aliases) == 0:
            raise ValidationError(f"Ingredient '{ing_id}' must have a non-empty list of aliases.")

        # Units check
        unit = item["default_unit"]
        if unit not in VALID_UNITS:
            raise ValidationError(f"Ingredient '{ing_id}' has unrecognized default_unit '{unit}'.")

        # Numeric fields
        price = item["price_inr_per_kg"]
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValidationError(f"Ingredient '{ing_id}' price_inr_per_kg must be a positive number.")

        if item.get("grams_per_piece") is not None:
            if not isinstance(item["grams_per_piece"], (int, float)) or item["grams_per_piece"] <= 0:
                raise ValidationError(f"Ingredient '{ing_id}' grams_per_piece must be positive if provided.")

        if item.get("ml_per_piece") is not None:
            if not isinstance(item["ml_per_piece"], (int, float)) or item["ml_per_piece"] <= 0:
                raise ValidationError(f"Ingredient '{ing_id}' ml_per_piece must be positive if provided.")

    print(f"[PASS] Validated {len(ingredients)} canonical ingredients.")
    return ingredient_ids


def validate_shelf_life(data_dir: Path, valid_ingredient_ids: set[str]) -> None:
    filepath = data_dir / "shelf_life.json"
    if not filepath.exists():
        raise ValidationError(f"Missing shelf_life.json at {filepath}")

    with open(filepath, encoding="utf-8") as f:
        try:
            shelf_life_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValidationError(f"shelf_life.json is not valid JSON: {e}") from e

    if not isinstance(shelf_life_data, list):
        raise ValidationError("shelf_life.json must contain a JSON array of records.")

    seen_pairs: set[tuple] = set()
    covered_ingredients: set[str] = set()

    for idx, record in enumerate(shelf_life_data):
        if not isinstance(record, dict):
            raise ValidationError(f"Shelf life record at index {idx} must be an object.")

        for req in ("ingredient_id", "storage"):
            if req not in record:
                raise ValidationError(f"Shelf life record at index {idx} missing '{req}'.")

        ing_id = record["ingredient_id"]
        if ing_id not in valid_ingredient_ids:
            raise ValidationError(f"Shelf life record at index {idx} references unknown ingredient '{ing_id}'.")

        storage = record["storage"]
        if storage not in VALID_STORAGES:
            raise ValidationError(f"Shelf life record for '{ing_id}' has invalid storage '{storage}'. Valid: {VALID_STORAGES}")

        pair = (ing_id, storage)
        if pair in seen_pairs:
            raise ValidationError(f"Duplicate shelf life storage record for ({ing_id}, {storage}).")
        seen_pairs.add(pair)
        covered_ingredients.add(ing_id)

        days = record.get("days")
        if days is not None and (not isinstance(days, int) or days < 0):
            raise ValidationError(f"Shelf life days for ({ing_id}, {storage}) must be a non-negative integer or null.")

        opened_days = record.get("opened_days")
        if opened_days is not None and (not isinstance(opened_days, int) or opened_days < 0):
            raise ValidationError(f"Shelf life opened_days for ({ing_id}, {storage}) must be a non-negative integer or null.")

    # Verify that all canonical ingredients have at least one shelf-life entry
    missing = valid_ingredient_ids - covered_ingredients
    if missing:
        raise ValidationError(f"{len(missing)} ingredients have no shelf_life entry: {list(missing)[:5]}...")

    print(f"[PASS] Validated {len(shelf_life_data)} shelf life entries across {len(covered_ingredients)} ingredients.")


def validate_recipes(data_dir: Path, valid_ingredient_ids: set[str]) -> None:
    filepath = data_dir / "recipes.json"
    if not filepath.exists():
        raise ValidationError(f"Missing recipes.json at {filepath}")

    with open(filepath, encoding="utf-8") as f:
        try:
            recipes = json.load(f)
        except json.JSONDecodeError as e:
            raise ValidationError(f"recipes.json is not valid JSON: {e}") from e

    if not isinstance(recipes, list):
        raise ValidationError("recipes.json must contain a JSON array.")

    if len(recipes) < 150:
        raise ValidationError(f"PRD requires at least 150 curated recipes, found {len(recipes)}.")

    recipe_ids: set[str] = set()
    north_indian_veg_count = 0
    south_indian_veg_count = 0
    non_veg_or_eggless_count = 0

    for idx, r in enumerate(recipes):
        if not isinstance(r, dict):
            raise ValidationError(f"Recipe at index {idx} must be an object.")

        for req in (
            "id",
            "title",
            "cuisine",
            "diet",
            "spice_level",
            "cooking_time_minutes",
            "base_servings",
            "ingredients",
            "steps",
            "nutrition_per_serving_estimate",
            "tags",
        ):
            if req not in r:
                raise ValidationError(f"Recipe '{r.get('id', idx)}' is missing required field '{req}'.")

        r_id = r["id"]
        if not isinstance(r_id, str) or not r_id.strip():
            raise ValidationError(f"Recipe at index {idx} has invalid id.")

        if r_id in recipe_ids:
            raise ValidationError(f"Duplicate recipe id '{r_id}' at index {idx}.")
        recipe_ids.add(r_id)

        # Diet & Spice checks
        diet = r["diet"]
        if diet not in VALID_DIETS:
            raise ValidationError(f"Recipe '{r_id}' has invalid diet '{diet}'.")

        spice = r["spice_level"]
        if spice not in VALID_SPICE_LEVELS:
            raise ValidationError(f"Recipe '{r_id}' has invalid spice_level '{spice}'.")

        # Step count: 3 to 12 steps (PRD Section 8.3 & 14.5)
        steps = r["steps"]
        if not isinstance(steps, list):
            raise ValidationError(f"Recipe '{r_id}' steps must be a list.")
        if len(steps) < 3 or len(steps) > 12:
            raise ValidationError(f"Recipe '{r_id}' has {len(steps)} steps. PRD requires between 3 and 12 steps.")

        # Ingredients validation & referential integrity
        ingredients = r["ingredients"]
        if not isinstance(ingredients, list) or len(ingredients) == 0:
            raise ValidationError(f"Recipe '{r_id}' must have at least one ingredient.")

        recipe_ing_ids: set[str] = set()
        for ing_idx, ing_item in enumerate(ingredients):
            if not isinstance(ing_item, dict):
                raise ValidationError(f"Recipe '{r_id}' ingredient at {ing_idx} must be an object.")

            for ifield in ("canonical_id", "qty", "unit", "is_optional"):
                if ifield not in ing_item:
                    raise ValidationError(f"Recipe '{r_id}' ingredient at {ing_idx} missing '{ifield}'.")

            c_id = ing_item["canonical_id"]
            if c_id not in valid_ingredient_ids:
                raise ValidationError(f"Recipe '{r_id}' references unknown canonical_id '{c_id}'.")

            if c_id in recipe_ing_ids:
                raise ValidationError(f"Recipe '{r_id}' contains duplicate ingredient '{c_id}'.")
            recipe_ing_ids.add(c_id)

            qty = ing_item["qty"]
            if not isinstance(qty, (int, float)) or qty <= 0:
                raise ValidationError(f"Recipe '{r_id}' ingredient '{c_id}' has invalid qty: {qty}")

        # Nutrition check
        nutrition = r["nutrition_per_serving_estimate"]
        if not isinstance(nutrition, dict):
            raise ValidationError(f"Recipe '{r_id}' nutrition_per_serving_estimate must be a dictionary.")
        for nut_field in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"):
            if nut_field not in nutrition:
                raise ValidationError(f"Recipe '{r_id}' nutrition missing '{nut_field}'.")

        # Cuisine & diet quota counts (PRD Section 8.3)
        cuisine = r["cuisine"]
        if cuisine == "North Indian" and diet in ("VEGETARIAN", "VEGAN"):
            north_indian_veg_count += 1
        elif cuisine == "South Indian" and diet in ("VEGETARIAN", "VEGAN"):
            south_indian_veg_count += 1

        if diet in ("EGGLESS", "NON_VEGETARIAN"):
            non_veg_or_eggless_count += 1

    # Check quotas:
    if north_indian_veg_count < 25:
        raise ValidationError(f"PRD requires >= 25 North Indian vegetarian recipes; found {north_indian_veg_count}.")

    if south_indian_veg_count < 25:
        raise ValidationError(f"PRD requires >= 25 South Indian vegetarian recipes; found {south_indian_veg_count}.")

    if non_veg_or_eggless_count < 15:
        raise ValidationError(f"PRD requires eggless and non-vegetarian options; found {non_veg_or_eggless_count}.")

    print(f"[PASS] Validated {len(recipes)} curated recipes (North Indian Veg: {north_indian_veg_count}, South Indian Veg: {south_indian_veg_count}, Non-Veg/Eggless: {non_veg_or_eggless_count}).")


def main() -> None:
    print("=" * 60)
    print("FridgeChef AI - Seed Data Validation")
    print("=" * 60)
    try:
        data_dir = find_data_dir()
        print(f"Validating data files in: {data_dir}")

        ingredient_ids = validate_ingredients(data_dir)
        validate_shelf_life(data_dir, ingredient_ids)
        validate_recipes(data_dir, ingredient_ids)

        print("=" * 60)
        print("SUCCESS: All seed data files strictly satisfy PRD requirements!")
        print("=" * 60)
    except ValidationError as e:
        print(f"\n[FAIL] VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
