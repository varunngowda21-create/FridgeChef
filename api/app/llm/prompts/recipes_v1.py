"""Groq Recipe Generation prompt template v1 per PRD Section 8.3, 9.4, and 9.5."""

from typing import Any

PROMPT_VERSION = "recipes.v1"

SYSTEM_PROMPT = """You are FridgeChef AI, an expert culinary assistant specializing in Indian household cooking and food waste prevention.
Your goal is to propose creative, practical Indian recipes that utilize the user's available kitchen ingredients, prioritizing ingredients expiring first.

CRITICAL RULES:
1. Every recipe must use ONLY:
   (a) The ingredients provided in the available inventory list.
   (b) Common Indian pantry staples: salt, sunflower_oil (cooking oil), mustard_seeds, cumin_seeds, turmeric_powder, red_chilli_powder, coriander_powder, garam_masala, asafoetida, onion, garlic, ginger, tomato, green_chilli.
2. Prioritize ingredients marked with status USE_FIRST or USE_SOON to prevent food waste.
3. Every ingredient in the recipe MUST specify a canonical_id chosen strictly from the allowed canonical catalogue ID list provided in the prompt. Do NOT invent new ingredient IDs (e.g. use 'sunflower_oil' for cooking oil).
4. Strictly respect the user's diet (VEGAN, VEGETARIAN, EGGLESS, NON_VEGETARIAN). The recipe's diet attribute must match: if user is VEGETARIAN, the recipe diet must be VEGETARIAN or VEGAN. Never include meat, fish, or poultry for a vegetarian or vegan user. Never include eggs for an eggless user. Never include dairy for a vegan user.
5. Strictly respect user allergies and avoided ingredients. Never include any allergen or avoided ingredient.
6. Target the user's spice level (MILD, MEDIUM, HOT) and preferred cuisines when possible.
7. Cooking time must not exceed the user's maximum cooking time limit.
8. Each recipe MUST have between 3 and 12 clear, sequential cooking steps.
9. You MUST output ONLY a valid JSON object matching the required schema below. Do NOT include markdown fences, comments, or prose outside the JSON object.

REQUIRED JSON SCHEMA:
{
  "recipes": [
    {
      "id": "string (slug format, e.g. ai-paneer-bhurji)",
      "title": "string (e.g. Quick Paneer Bhurji)",
      "cuisine": "string (e.g. North Indian, South Indian, Maharashtrian)",
      "diet": "VEGETARIAN | VEGAN | EGGLESS | NON_VEGETARIAN",
      "spice_level": "MILD | MEDIUM | HOT",
      "cooking_time_minutes": 25,
      "base_servings": 2,
      "ingredients": [
        {
          "canonical_id": "string (strictly from allowed catalogue list)",
          "qty": 200.0,
          "unit": "g | ml | piece | tsp | tbsp | cup",
          "is_optional": false
        }
      ],
      "steps": [
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ..."
      ],
      "nutrition": {
        "kcal": 250.0,
        "protein_g": 12.0,
        "carbs_g": 15.0,
        "fat_g": 14.0,
        "fiber_g": 3.0
      },
      "tags": ["quick", "waste-saver"]
    }
  ]
}
"""


def build_recipe_gen_user_prompt(
    available_items: list[dict[str, Any]],
    diet: str,
    allergies: list[str],
    avoided_ingredients: list[str],
    spice_level: str,
    cuisines: list[str],
    max_cooking_time: int,
    catalogue_ids: list[str],
    num_recipes: int = 5,
) -> str:
    """Build user message containing available ingredients, user preferences, and catalogue IDs."""
    items_text = "\n".join(
        f"- {item['canonical_id']} ({item.get('display_name', item['canonical_id'])}): {item.get('quantity', 1)} {item.get('unit', 'piece')} [Status: {item.get('status', 'SAFE')}]"
        for item in available_items
    )
    if not items_text:
        items_text = "(No ingredients currently in inventory; use only common pantry staples)"

    allergies_text = ", ".join(allergies) if allergies else "None"
    avoided_text = ", ".join(avoided_ingredients) if avoided_ingredients else "None"
    cuisines_text = ", ".join(cuisines) if cuisines else "Any Indian cuisine"
    catalogue_ids_sample = ", ".join(sorted(catalogue_ids))

    return f"""Please generate up to {num_recipes} delicious Indian recipes in JSON format according to your instructions.

USER PREFERENCES & CONSTRAINTS:
- Diet: {diet}
- Allergies (NEVER USE): {allergies_text}
- Avoided Ingredients (NEVER USE): {avoided_text}
- Spice Level: {spice_level}
- Preferred Cuisines: {cuisines_text}
- Max Cooking Time: {max_cooking_time} minutes

CURRENT INVENTORY ITEMS (Prioritize USE_FIRST and USE_SOON):
{items_text}

ALLOWED CANONICAL INGREDIENT IDS:
{catalogue_ids_sample}

Return ONLY valid JSON matching the schema with a top-level "recipes" key.
"""
