from pathlib import Path

import pytest

from scripts.validate_data import (
    ValidationError,
    find_data_dir,
    validate_ingredients,
    validate_recipes,
    validate_shelf_life,
)


def test_seed_files_pass_validation():
    data_dir = find_data_dir()
    ing_ids = validate_ingredients(data_dir)
    assert len(ing_ids) >= 200

    validate_shelf_life(data_dir, ing_ids)
    validate_recipes(data_dir, ing_ids)


def test_validator_rejects_missing_field(tmp_path: Path):
    import json
    invalid_data = [{"id": "bad_item"}]  # Missing display_name, category, etc.
    data_file = tmp_path / "ingredients.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(invalid_data, f)

    with pytest.raises(ValidationError):
        validate_ingredients(tmp_path)
