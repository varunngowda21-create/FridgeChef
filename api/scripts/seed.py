#!/usr/bin/env python3
"""
Seed script for FridgeChef AI database.
Loads canonical ingredients, shelf life, and curated recipes into PostgreSQL.
PRD References: Section 8.3, 10.2, 10.3, 14.5.
"""

import sys
from pathlib import Path

# Add api to sys.path
API_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(API_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.services.recipe_catalogue import seed_catalogue_data  # noqa: E402


def main() -> None:
    print("=" * 60)
    print("FridgeChef AI - Seeding Catalogue Data")
    print("=" * 60)

    db = SessionLocal()
    try:
        ings, sls, recs = seed_catalogue_data(db)
        print("[SUCCESS] Successfully seeded database:")
        print(f" - Canonical Ingredients: {ings}")
        print(f" - Shelf Life Records:    {sls}")
        print(f" - Curated Recipes:        {recs}")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"[FAIL] Error seeding database: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
