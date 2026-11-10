"""Locust load test suite for FridgeChef AI per PRD Section 7.1 and 14.7.

Simulates 100 concurrent users against non-AI read endpoints and cached recommendations.
"""

import json
from pathlib import Path

from locust import HttpUser, between, task

USERS_FILE = Path(__file__).resolve().parent / "load_users.json"


def load_test_users():
    if not USERS_FILE.exists():
        raise RuntimeError(f"Missing {USERS_FILE}. Run setup_load_data.py first.")
    with open(USERS_FILE, encoding="utf-8") as f:
        return json.load(f)


_ALL_USERS = load_test_users()
_USER_INDEX = 0


class FridgeChefUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        global _USER_INDEX
        user_idx = _USER_INDEX % len(_ALL_USERS)
        _USER_INDEX += 1
        self.user_data = _ALL_USERS[user_idx]
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.user_data['token']}",
        }

    @task(3)
    def view_dashboard(self):
        with self.client.get(
            "/api/v1/dashboard",
            headers=self.headers,
            name="/api/v1/dashboard",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 429:
                res.success()  # Intentional rate limit response per PRD NFR-022
            else:
                res.failure(f"Unexpected status: {res.status_code}")

    @task(3)
    def view_inventory(self):
        with self.client.get(
            "/api/v1/inventory",
            headers=self.headers,
            name="/api/v1/inventory",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 429:
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")

    @task(2)
    def view_cached_recommendations(self):
        with self.client.get(
            "/api/v1/recommendations?limit=5&servings=2",
            headers=self.headers,
            name="/api/v1/recommendations (cached)",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 429:
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")

    @task(2)
    def view_recipe_detail(self):
        with self.client.get(
            "/api/v1/recipes/aloo_gobi?servings=2",
            headers=self.headers,
            name="/api/v1/recipes/{id}",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 429:
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")

    @task(1)
    def check_health(self):
        with self.client.get(
            "/api/health",
            name="/api/health",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"Unexpected status: {res.status_code}")

