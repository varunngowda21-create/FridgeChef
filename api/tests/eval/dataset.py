"""Dataset loader and scenario definitions for vision evaluation."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_SCENARIOS_JSON = EVAL_DIR / "data" / "scenarios.json"
DEFAULT_IMAGES_DIR = EVAL_DIR / "images"

# 30 Common Indian Ingredients per PRD Section 14.4
TARGET_30_INDIAN_INGREDIENTS = [
    "onion", "tomato", "potato", "green_chilli", "ginger", "garlic",
    "coriander_leaves", "curry_leaves", "capsicum", "carrot", "green_peas",
    "paneer", "curd", "milk", "ghee", "butter", "lemon", "cucumber",
    "cauliflower", "spinach", "cabbage", "okra", "eggs", "chicken_curry_cut",
    "mushroom", "coconut_fresh", "mint_leaves", "fenugreek_leaves", "apple", "banana"
]


@dataclass
class EvaluationScenario:
    id: str
    title: str
    description: str
    environment: str
    lighting: str
    clutter: str
    image_filename: str
    expected_canonical_ids: list[str]
    stored_vision_output: dict[str, Any]
    notes: str = ""

    def get_image_path(self, images_dir: Path | None = None) -> Path:
        base = images_dir or DEFAULT_IMAGES_DIR
        return base / self.image_filename

    def load_image_bytes(self, images_dir: Path | None = None) -> bytes:
        img_path = self.get_image_path(images_dir)
        if not img_path.exists():
            raise FileNotFoundError(f"Scenario image not found: {img_path}")
        return img_path.read_bytes()


def load_evaluation_scenarios(scenarios_json: Path | None = None) -> list[EvaluationScenario]:
    """Load and parse evaluation scenarios from JSON."""
    target_path = scenarios_json or DEFAULT_SCENARIOS_JSON
    if not target_path.exists():
        raise FileNotFoundError(f"Evaluation scenarios file not found at {target_path}")

    raw_list = json.loads(target_path.read_text(encoding="utf-8"))
    scenarios: list[EvaluationScenario] = []
    for item in raw_list:
        scenarios.append(
            EvaluationScenario(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                environment=item["environment"],
                lighting=item["lighting"],
                clutter=item["clutter"],
                image_filename=item["image_filename"],
                expected_canonical_ids=item["expected_canonical_ids"],
                stored_vision_output=item["stored_vision_output"],
                notes=item.get("notes", ""),
            )
        )
    return scenarios


def validate_scenarios(
    scenarios: list[EvaluationScenario],
    valid_canonical_ids: set[str],
    images_dir: Path | None = None,
) -> list[str]:
    """Validate referential integrity of scenarios against canonical ingredients and disk assets.

    Returns a list of error strings (empty if valid).
    """
    errors: list[str] = []
    seen_ids: set[str] = set()

    for sc in scenarios:
        if sc.id in seen_ids:
            errors.append(f"Duplicate scenario ID: {sc.id}")
        seen_ids.add(sc.id)

        # Verify all expected canonical IDs exist in canonical catalogue
        for expected_id in sc.expected_canonical_ids:
            if expected_id not in valid_canonical_ids:
                errors.append(f"Scenario {sc.id} specifies unknown canonical ID: '{expected_id}'")

        # Verify image file exists
        img_path = sc.get_image_path(images_dir)
        if not img_path.exists():
            errors.append(f"Scenario {sc.id} image missing on disk: {img_path}")

        # Verify stored vision output schema has 'items'
        if "items" not in sc.stored_vision_output:
            errors.append(f"Scenario {sc.id} stored_vision_output missing 'items' key")

    return errors

