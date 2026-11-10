"""Dashboard service per PRD Section 6.8, 11.10, 12.3, FR-070, and FR-071."""

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import MealPlanNotFoundError
from app.db.models.auth import User
from app.db.models.inventory import InventoryItem
from app.schemas.dashboard import (
    ActivePlanSummary,
    DashboardResponse,
    FreshnessStatusCounts,
)
from app.services.freshness import FreshnessStatus, get_freshness_for_item
from app.services.impact import get_month_to_date_impact
from app.services.planner import get_active_meal_plan
from app.services.recommendations import get_recommendations

logger = logging.getLogger("fridgechef.dashboard")


async def get_dashboard_data(
    db: Session,
    user: User,
    settings: Settings | None = None,
) -> DashboardResponse:
    """Synthesize freshness status counts, top recommendations, active plan summary,

    and month-to-date impact metrics for authenticated user.
    """
    if settings is None:
        settings = get_settings()

    # 1. Freshness status counts across active inventory items
    active_items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.user_id == user.id,
            InventoryItem.archived_at.is_(None),
            InventoryItem.quantity > 0,
        )
        .all()
    )

    use_first = 0
    use_soon = 0
    safe = 0
    today = date.today()

    for item in active_items:
        try:
            freshness = get_freshness_for_item(
                db=db,
                ingredient_id=item.ingredient_id or "",
                storage=item.storage,
                added_on=item.added_on,
                opened_on=item.opened_on,
                today=today,
            )
            if freshness.status == FreshnessStatus.USE_FIRST:
                use_first += 1
            elif freshness.status == FreshnessStatus.USE_SOON:
                use_soon += 1
            else:
                safe += 1
        except Exception:
            safe += 1

    status_counts = FreshnessStatusCounts(
        USE_FIRST=use_first,
        USE_SOON=use_soon,
        SAFE=safe,
        TOTAL=len(active_items),
    )

    # 2. Recommendations (limit parameterized via DASHBOARD_RECOMMENDATIONS_LIMIT)
    try:
        rec_resp = await get_recommendations(
            db=db,
            user=user,
            limit=settings.DASHBOARD_RECOMMENDATIONS_LIMIT,
            settings=settings,
            active_items=active_items,
        )
        recommendations = rec_resp.items
    except Exception as exc:
        logger.warning(f"Failed to fetch recommendations for dashboard: {exc}")
        recommendations = []

    # 3. Active meal plan summary
    active_plan: ActivePlanSummary | None = None
    try:
        plan_resp = get_active_meal_plan(db=db, user=user)
        today_iso = today.isoformat()
        today_meals = [
            s for s in plan_resp.plan.get("slots", [])
            if s.get("date") == today_iso
        ]
        active_plan = ActivePlanSummary(
            id=plan_resp.id,
            start_date=plan_resp.start_date,
            days_count=7,
            low_variety=plan_resp.low_variety,
            today_meals=today_meals,
        )
    except MealPlanNotFoundError:
        active_plan = None
    except Exception as exc:
        logger.warning(f"Error fetching active meal plan for dashboard: {exc}")
        active_plan = None

    # 4. Month-to-date impact metrics
    impact = get_month_to_date_impact(db=db, user_id=user.id)

    return DashboardResponse(
        status_counts=status_counts,
        recommendations=recommendations,
        active_plan=active_plan,
        impact=impact,
    )
