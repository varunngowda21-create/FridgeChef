from pydantic import BaseModel, ConfigDict, Field


class ShelfLifeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage: str
    days: int | None = None
    opened_days: int | None = None


class IngredientOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    display_name: str
    category: str
    aliases: list[str]
    default_unit: str
    grams_per_piece: float | None = None
    ml_per_piece: float | None = None
    price_inr_per_kg: float
    allergen_group: str | None = None
    shelf_life: list[ShelfLifeItem] = Field(default_factory=list)


class IngredientListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[IngredientOut]
    next_cursor: str | None = None


class RecipeIngredientOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    display_name: str
    qty: float
    unit: str
    is_optional: bool


class NutritionEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float


class RecipeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    cuisine: str
    diet: str
    spice_level: str
    cooking_time_minutes: int
    base_servings: int
    scaled_servings: int
    nutrition_per_serving: NutritionEstimate
    ingredients: list[RecipeIngredientOut]
    steps: list[str]
    tags: list[str]
    source: str
