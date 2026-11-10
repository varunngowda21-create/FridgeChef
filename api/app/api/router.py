from fastapi import APIRouter

from app.api.routes import (
    auth,
    catalogue,
    dashboard,
    health,
    inventory,
    me,
    meal_plans,
    recipes,
    recommendations,
    scans,
    shopping,
)

api_v1_router = APIRouter(prefix="/api/v1")

# Mount routes to /api/v1
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(me.router)
api_v1_router.include_router(inventory.router)
api_v1_router.include_router(catalogue.router)
api_v1_router.include_router(scans.router)
api_v1_router.include_router(recommendations.router)
api_v1_router.include_router(recipes.router)
api_v1_router.include_router(meal_plans.router)
api_v1_router.include_router(shopping.router)
api_v1_router.include_router(dashboard.router)
