import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Ingredient(Base, TimestampMixin):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aliases: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    default_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    grams_per_piece: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    ml_per_piece: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_inr_per_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    allergen_group: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    shelf_lives: Mapped[list["ShelfLife"]] = relationship(
        "ShelfLife", back_populates="ingredient", cascade="all, delete-orphan"
    )
    recipe_usages: Mapped[list["RecipeIngredient"]] = relationship(
        "RecipeIngredient", back_populates="ingredient"
    )


class ShelfLife(Base, TimestampMixin):
    __tablename__ = "shelf_life"
    __table_args__ = (
        UniqueConstraint("ingredient_id", "storage", name="uq_shelf_life_ingredient_storage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ingredient_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage: Mapped[str] = mapped_column(String(50), nullable=False)
    days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ingredient: Mapped["Ingredient"] = relationship("Ingredient", back_populates="shelf_lives")


class Recipe(Base, TimestampMixin):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    cuisine: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    diet: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    spice_level: Mapped[str] = mapped_column(String(50), nullable=False)
    cooking_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    base_servings: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    steps: Mapped[list] = mapped_column(JSONB, nullable=False)
    nutrition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="CURATED", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="APPROVED", nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeIngredient(Base, TimestampMixin):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recipe_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Explicit index per PRD Section 10
    ingredient_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("ingredients.id"), nullable=False, index=True
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship("Ingredient", back_populates="recipe_usages")
