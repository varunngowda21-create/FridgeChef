#!/usr/bin/env python3
"""
Full Recipe Assembler for FridgeChef AI
Combines recipes from build_recipes.py and build_recipes_part2.py,
normalizes canonical ingredient IDs to match ingredients.json,
checks constraints, and writes api/data/recipes.json.
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from build_recipes import RECIPES as PART1_RECIPES  # noqa: E402
from build_recipes_part2 import ADDITIONAL_RECIPES as PART2_RECIPES  # noqa: E402

DATA_DIR = SCRIPT_DIR.parent / "data"

with open(DATA_DIR / "ingredients.json", encoding="utf-8") as f:
    VALID_ING_IDS = {ing["id"] for ing in json.load(f)}

CANONICAL_ID_MAP = {
    "ladies_finger": "okra",
    "white_pumpkin": "ash_gourd",
    "yellow_pumpkin": "pumpkin",
    "sooji": "semolina",
    "semiya": "vermicelli",
    "chana_white": "kabuli_chana",
    "moong_dal_yellow": "yellow_moong_dal",
    "moong_dal_whole": "whole_green_moong",
    "urad_dal_white": "urad_dal_split",
    "matki": "moth_beans",
    "sesame_seeds": "white_sesame_seeds",
    "coconut_grated": "coconut_fresh",
    "green_cardamom": "cardamom_green",
    "cardamom_powder": "cardamom_green",
    "black_cardamom": "cardamom_black",
    "black_pepper_whole": "black_peppercorns",
    "kashmiri_red_chilli": "dry_red_chillies",
    "kashmiri_red_chilli_powder": "kashmiri_chilli_powder",
    "kalonji": "nigella_seeds",
    "soya_sauce": "soy_sauce",
    "chicken": "chicken_curry_cut",
    "mutton": "mutton_curry_cut",
    "fish": "fish_rohu",
}

ALL_RAW_RECIPES = PART1_RECIPES + PART2_RECIPES
print(f"Total candidate recipes to assemble: {len(ALL_RAW_RECIPES)}")

NORMALIZED_RECIPES = []
seen_ids = set()
errors = []

for _idx, r in enumerate(ALL_RAW_RECIPES):
    rid = r["id"]
    if rid in seen_ids:
        errors.append(f"Duplicate recipe ID: {rid}")
    seen_ids.add(rid)

    # Normalize ingredients
    norm_ingredients = []
    seen_ings = set()
    for ing in r["ingredients"]:
        raw_cid = ing["canonical_id"]
        cid = CANONICAL_ID_MAP.get(raw_cid, raw_cid)
        if cid not in VALID_ING_IDS:
            errors.append(f"Recipe '{rid}' references invalid canonical_id '{cid}' (was '{raw_cid}')")
        if cid in seen_ings:
            # If mapped to existing ingredient in recipe (e.g. green cardamom and cardamom powder), merge or skip
            for existing in norm_ingredients:
                if existing["canonical_id"] == cid:
                    existing["qty"] += ing["qty"]
                    break
        else:
            seen_ings.add(cid)
            norm_ingredients.append({
                "canonical_id": cid,
                "qty": ing["qty"],
                "unit": ing["unit"],
                "is_optional": ing["is_optional"]
            })

    # Step count
    if len(r["steps"]) < 3 or len(r["steps"]) > 12:
        errors.append(f"Recipe '{rid}' has {len(r['steps'])} steps; must be between 3 and 12.")

    r_copy = dict(r)
    r_copy["ingredients"] = norm_ingredients
    NORMALIZED_RECIPES.append(r_copy)

if errors:
    print(f"FAILED validation with {len(errors)} errors:")
    for e in errors[:15]:
        print(" -", e)
    sys.exit(1)

out_file = DATA_DIR / "recipes.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(NORMALIZED_RECIPES, f, indent=2, ensure_ascii=False)

print(f"SUCCESS: Wrote {len(NORMALIZED_RECIPES)} fully validated recipes to {out_file}!")
