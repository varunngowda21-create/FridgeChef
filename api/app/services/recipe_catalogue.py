import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.catalogue import Ingredient, Recipe, RecipeIngredient, ShelfLife

logger = logging.getLogger(__name__)


def find_data_dir() -> Path:
    candidates = [
        Path(__file__).parent.parent.parent / "data",
        Path.cwd() / "data",
        Path.cwd() / "api" / "data",
    ]
    for c in candidates:
        if c.is_dir() and (c / "ingredients.json").exists():
            return c
    raise FileNotFoundError("Could not find data directory containing ingredients.json")


def seed_catalogue_data(db: Session, data_dir: Path | None = None) -> tuple[int, int, int]:
    """
    Idempotent loader for ingredients, shelf life, and curated recipes.
    Returns (num_ingredients, num_shelf_life, num_recipes).
    """
    if data_dir is None:
        data_dir = find_data_dir()

    logger.info("Loading seed data from %s", data_dir)

    # 1. Seed Ingredients
    with open(data_dir / "ingredients.json", encoding="utf-8") as f:
        ingredients_raw: list[dict[str, Any]] = json.load(f)

    existing_ing_ids = set(db.scalars(select(Ingredient.id)).all())
    ing_count = 0

    for item in ingredients_raw:
        ing_id = item["id"]
        grams = Decimal(str(item["grams_per_piece"])) if item.get("grams_per_piece") is not None else None
        mls = Decimal(str(item["ml_per_piece"])) if item.get("ml_per_piece") is not None else None
        price = Decimal(str(item["price_inr_per_kg"]))

        if ing_id in existing_ing_ids:
            ing = db.get(Ingredient, ing_id)
            if ing:
                ing.display_name = item["display_name"]
                ing.category = item["category"]
                ing.aliases = item["aliases"]
                ing.default_unit = item["default_unit"]
                ing.grams_per_piece = grams
                ing.ml_per_piece = mls
                ing.price_inr_per_kg = price
                ing.allergen_group = item.get("allergen_group")
        else:
            new_ing = Ingredient(
                id=ing_id,
                display_name=item["display_name"],
                category=item["category"],
                aliases=item["aliases"],
                default_unit=item["default_unit"],
                grams_per_piece=grams,
                ml_per_piece=mls,
                price_inr_per_kg=price,
                allergen_group=item.get("allergen_group"),
            )
            db.add(new_ing)
            existing_ing_ids.add(ing_id)
        ing_count += 1

    db.flush()
    logger.info("Upserted %d ingredients.", ing_count)

    # 2. Seed Shelf Life
    with open(data_dir / "shelf_life.json", encoding="utf-8") as f:
        shelf_life_raw: list[dict[str, Any]] = json.load(f)

    existing_sl = {
        (sl.ingredient_id, sl.storage): sl
        for sl in db.scalars(select(ShelfLife)).all()
    }
    sl_count = 0

    for rec in shelf_life_raw:
        key = (rec["ingredient_id"], rec["storage"])
        if key in existing_sl:
            sl_entry = existing_sl[key]
            sl_entry.days = rec.get("days")
            sl_entry.opened_days = rec.get("opened_days")
        else:
            new_sl = ShelfLife(
                ingredient_id=rec["ingredient_id"],
                storage=rec["storage"],
                days=rec.get("days"),
                opened_days=rec.get("opened_days"),
            )
            db.add(new_sl)
            existing_sl[key] = new_sl
        sl_count += 1

    db.flush()
    logger.info("Upserted %d shelf life records.", sl_count)

    # 3. Seed Recipes
    with open(data_dir / "recipes.json", encoding="utf-8") as f:
        recipes_raw: list[dict[str, Any]] = json.load(f)

    existing_recipes = {r.id: r for r in db.scalars(select(Recipe)).all()}
    recipe_count = 0

    for r_data in recipes_raw:
        r_id = r_data["id"]
        if r_id in existing_recipes:
            recipe = existing_recipes[r_id]
            recipe.title = r_data["title"]
            recipe.cuisine = r_data["cuisine"]
            recipe.diet = r_data["diet"]
            recipe.spice_level = r_data["spice_level"]
            recipe.cooking_time_minutes = r_data["cooking_time_minutes"]
            recipe.base_servings = r_data.get("base_servings", 2)
            recipe.steps = r_data["steps"]
            recipe.nutrition = r_data["nutrition_per_serving_estimate"]
            recipe.tags = r_data.get("tags", [])
            recipe.source = "CURATED"
            recipe.status = "APPROVED"

            # Remove existing ingredients and re-add to maintain integrity
            recipe.ingredients.clear()
        else:
            recipe = Recipe(
                id=r_id,
                title=r_data["title"],
                cuisine=r_data["cuisine"],
                diet=r_data["diet"],
                spice_level=r_data["spice_level"],
                cooking_time_minutes=r_data["cooking_time_minutes"],
                base_servings=r_data.get("base_servings", 2),
                steps=r_data["steps"],
                nutrition=r_data["nutrition_per_serving_estimate"],
                tags=r_data.get("tags", []),
                source="CURATED",
                status="APPROVED",
            )
            db.add(recipe)
            existing_recipes[r_id] = recipe

        db.flush()

        # Add recipe ingredients
        for ing in r_data["ingredients"]:
            ri = RecipeIngredient(
                recipe_id=r_id,
                ingredient_id=ing["canonical_id"],
                qty=Decimal(str(ing["qty"])),
                unit=ing["unit"],
                is_optional=ing.get("is_optional", False),
            )
            db.add(ri)

        recipe_count += 1

    db.commit()
    logger.info("Upserted %d curated recipes with ingredient mappings.", recipe_count)
    return (ing_count, sl_count, recipe_count)
