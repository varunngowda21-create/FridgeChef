#!/usr/bin/env python3
"""
Load Test Environment Setup & User Provisioning.
Provisions 100 deterministic test users with preferences, inventory, and cached recommendations
for load testing (k6, Locust, and Python concurrent harness) per PRD Section 7.1 and 14.7.
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Add api directory to sys.path
API_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(API_DIR))

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.models.analytics import RecommendationCache  # noqa: E402
from app.db.models.auth import User, UserPreference  # noqa: E402
from app.db.models.inventory import InventoryItem  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.recommendations import compute_cache_key  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load_setup")

OUTPUT_FILE = Path(__file__).resolve().parent / "load_users.json"
LOAD_USER_PREFIX = "loadtest_user_"
USER_COUNT = 100
DEFAULT_PASSWORD = "Password123!"

STANDARD_INVENTORY = [
    {"ingredient_id": "tomato", "display_name": "Tomato", "quantity": 4, "unit": "piece", "storage": "FRIDGE"},
    {"ingredient_id": "potato", "display_name": "Potato", "quantity": 3, "unit": "piece", "storage": "PANTRY"},
    {"ingredient_id": "onion", "display_name": "Onion", "quantity": 4, "unit": "piece", "storage": "PANTRY"},
    {"ingredient_id": "green_chilli", "display_name": "Green Chilli", "quantity": 6, "unit": "piece", "storage": "FRIDGE"},
    {"ingredient_id": "ginger", "display_name": "Ginger", "quantity": 50, "unit": "g", "storage": "FRIDGE"},
    {"ingredient_id": "curd", "display_name": "Curd", "quantity": 500, "unit": "g", "storage": "FRIDGE"},
    {"ingredient_id": "paneer", "display_name": "Paneer", "quantity": 200, "unit": "g", "storage": "FRIDGE"},
]

SAMPLE_RECIPE_PAYLOAD = {
    "cache": "HIT",
    "degraded": False,
    "generated_at": "2026-11-01T12:00:00Z",
    "items": [
        {
            "recipe_id": "aloo_gobi",
            "title": "Aloo Gobi",
            "cuisine": "North Indian",
            "cooking_time_minutes": 30,
            "servings": 2,
            "match_percent": 85,
            "source": "CURATED",
            "uses_expiring": [
                {"canonical_id": "potato", "status": "SAFE", "days_left": 14}
            ],
            "missing": [
                {"canonical_id": "cauliflower", "qty": 300.0, "unit": "g", "est_cost_inr": 30.0}
            ],
            "missing_cost_inr": 30.0,
            "reason": "Uses your fresh potatoes and onions with common pantry spices.",
        },
        {
            "recipe_id": "paneer_bhurji",
            "title": "Paneer Bhurji",
            "cuisine": "North Indian",
            "cooking_time_minutes": 20,
            "servings": 2,
            "match_percent": 90,
            "source": "CURATED",
            "uses_expiring": [
                {"canonical_id": "paneer", "status": "SAFE", "days_left": 4},
                {"canonical_id": "tomato", "status": "SAFE", "days_left": 7}
            ],
            "missing": [],
            "missing_cost_inr": 0.0,
            "reason": "Quick high-protein dinner using fresh paneer and tomatoes.",
        }
    ]
}


def cleanup_load_users() -> int:
    """Safely remove all load test users and cascading records."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.like(f"{LOAD_USER_PREFIX}%")).all()
        count = len(users)
        for u in users:
            # Delete dependent records
            db.query(RecommendationCache).filter(RecommendationCache.user_id == u.id).delete()
            db.query(InventoryItem).filter(InventoryItem.user_id == u.id).delete()
            db.query(UserPreference).filter(UserPreference.user_id == u.id).delete()
            db.delete(u)
        db.commit()
        if OUTPUT_FILE.exists():
            OUTPUT_FILE.unlink()
        logger.info(f"Cleaned up {count} existing load test users.")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up load test users: {e}")
        raise
    finally:
        db.close()


def provision_load_users(user_count: int = USER_COUNT) -> list[dict]:
    """Create deterministic users with preferences, inventory, and pre-computed cache."""
    cleanup_load_users()

    db = SessionLocal()
    users_data = []

    try:
        logger.info(f"Hashing template password for {user_count} load test users...")
        pwd_hash = hash_password(DEFAULT_PASSWORD)
        today = date.today()
        now = datetime.now(timezone.utc)

        for i in range(user_count):
            user_id = uuid.uuid4()
            email = f"{LOAD_USER_PREFIX}{i:03d}@example.com"
            display_name = f"Load User {i:03d}"

            # 1. User account
            user = User(
                id=user_id,
                email=email,
                password_hash=pwd_hash,
                display_name=display_name,
            )
            db.add(user)
            db.flush()

            # 2. Preferences
            pref = UserPreference(
                user_id=user_id,
                household_size=2,
                diet="VEGETARIAN",
                spice_level="MEDIUM",
                cuisines=["North Indian", "South Indian"],
                max_cooking_time=45,
                allergies=[],
                avoided_ingredients=[],
                version=1,
            )
            db.add(pref)

            # 3. Inventory items
            user_inv_items = []
            for item_spec in STANDARD_INVENTORY:
                inv_item = InventoryItem(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    ingredient_id=item_spec["ingredient_id"],
                    display_name=item_spec["display_name"],
                    quantity=Decimal(f"{item_spec['quantity']:.2f}"),
                    unit=item_spec["unit"],
                    storage=item_spec["storage"],
                    added_on=today,
                )
                db.add(inv_item)
                user_inv_items.append(inv_item)

            # 4. Pre-populated Recommendation Cache (per PRD NFR-003 cached path)
            # 4a. Dashboard query (limit=3, target_servings=2 per DASHBOARD_RECOMMENDATIONS_LIMIT)
            cache_key_dashboard = compute_cache_key(
                inventory_items=user_inv_items,
                preferences_version=1,
                diet="VEGETARIAN",
                max_cooking_time=45,
                household_size=2,
                target_servings=2,
                limit=3,
            )
            rec_cache_dash = RecommendationCache(
                user_id=user_id,
                cache_key=cache_key_dashboard,
                payload=SAMPLE_RECIPE_PAYLOAD,
                expires_at=now + timedelta(days=7),
            )
            db.add(rec_cache_dash)

            # 4b. Recommendations view query (limit=5, target_servings=2)
            cache_key_recs = compute_cache_key(
                inventory_items=user_inv_items,
                preferences_version=1,
                diet="VEGETARIAN",
                max_cooking_time=45,
                household_size=2,
                target_servings=2,
                limit=5,
            )
            rec_cache_recs = RecommendationCache(
                user_id=user_id,
                cache_key=cache_key_recs,
                payload=SAMPLE_RECIPE_PAYLOAD,
                expires_at=now + timedelta(days=7),
            )
            db.add(rec_cache_recs)

            # 5. Generate valid JWT access token
            token = create_access_token(user_id=user_id, email=email)

            users_data.append({
                "index": i,
                "user_id": str(user_id),
                "email": email,
                "token": token,
                "display_name": display_name,
            })

            db.commit()

        logger.info(f"Successfully provisioned {len(users_data)} load test users in PostgreSQL.")

        # Save tokens for k6 and Locust
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=2)
        logger.info(f"Saved load test credentials to {OUTPUT_FILE}")

        return users_data
    except Exception as e:
        db.rollback()
        logger.error(f"Failed provisioning load test users: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="FridgeChef Load Test Data Setup")
    parser.add_argument("--cleanup", action="store_true", help="Remove all load test users and credentials file")
    parser.add_argument("--users", type=int, default=USER_COUNT, help="Number of load test users to provision (default: 100)")
    args = parser.parse_args()

    if args.cleanup:
        cleanup_load_users()
    else:
        provision_load_users(args.users)


if __name__ == "__main__":
    main()
