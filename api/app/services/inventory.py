import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.analytics import RecommendationCache
from app.db.models.auth import User
from app.db.models.catalogue import Ingredient
from app.db.models.inventory import InventoryItem, WasteLog
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryListResponse,
    InventoryUseResponse,
    InventoryWasteResponse,
)
from app.services.freshness import (
    FreshnessResult,
    FreshnessStatus,
    get_freshness_for_item,
)
from app.services.units import calculate_estimated_cost, normalize_unit


def to_inventory_item_response(
    item: InventoryItem,
    freshness: FreshnessResult,
) -> InventoryItemResponse:
    """Format an InventoryItem database model and FreshnessResult into an API response schema."""
    return InventoryItemResponse(
        id=item.id,
        user_id=item.user_id,
        ingredient_id=item.ingredient_id,
        display_name=item.display_name,
        quantity=item.quantity,
        unit=item.unit,
        storage=item.storage,
        added_on=item.added_on,
        opened_on=item.opened_on,
        shelf_life_days_estimate=item.shelf_life_days_estimate,
        expires_on=item.expires_on,
        days_left=freshness.days_left,
        days_left_display=freshness.days_left_display,
        status=freshness.status.value,
        archived_at=item.archived_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def create_inventory_item(
    db: Session,
    user: User,
    data: InventoryItemCreate,
) -> InventoryItemResponse:
    """Create a new inventory item with canonical ingredient verification and freshness calculation."""
    # 1. Verify canonical ingredient existence in catalogue
    ingredient = (
        db.query(Ingredient)
        .filter(Ingredient.id == data.canonical_id)
        .first()
    )
    if not ingredient:
        raise AppError(
            code="INGREDIENT_NOT_FOUND",
            message=f"Canonical ingredient '{data.canonical_id}' not found.",
            status_code=404,
        )

    # 2. Date validation
    added_on = data.added_on or date.today()
    if added_on > date.today():
        raise AppError(
            code="INVALID_DATE",
            message="Added date cannot be in the future.",
            status_code=422,
        )

    # 3. Freshness calculation (rejects non-applicable storage)
    freshness = get_freshness_for_item(
        db=db,
        ingredient_id=ingredient.id,
        storage=data.storage,
        added_on=added_on,
        opened_on=data.opened_on,
    )

    display_name = data.display_name.strip() if data.display_name else ingredient.display_name
    unit = normalize_unit(data.unit)

    # 4. Create and persist model
    item = InventoryItem(
        user_id=user.id,
        ingredient_id=ingredient.id,
        display_name=display_name,
        quantity=data.quantity,
        unit=unit,
        storage=data.storage.strip().upper(),
        added_on=added_on,
        opened_on=data.opened_on,
        shelf_life_days_estimate=freshness.base_life,
        expires_on=freshness.expires_on,
        archived_at=None,
    )
    db.add(item)

    # Invalidate recommendation cache (PRD FR-046)
    db.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).delete()

    db.commit()
    db.refresh(item)

    return to_inventory_item_response(item=item, freshness=freshness)


def list_inventory_items(
    db: Session,
    user: User,
    status_filter: str | None = None,
    storage_filter: str | None = None,
    sort_by: str = "expiry",
    limit: int = 50,
    cursor: str | None = None,
) -> InventoryListResponse:
    """List non-archived inventory items for authenticated user with computed freshness."""
    query = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.archived_at.is_(None),
    )

    if storage_filter:
        query = query.filter(InventoryItem.storage == storage_filter.strip().upper())

    # Sorting
    if sort_by == "name":
        query = query.order_by(InventoryItem.display_name.asc(), InventoryItem.id.asc())
    elif sort_by == "added":
        query = query.order_by(InventoryItem.added_on.desc(), InventoryItem.id.asc())
    else:  # default 'expiry'
        query = query.order_by(
            InventoryItem.expires_on.asc().nulls_last(),
            InventoryItem.added_on.asc(),
            InventoryItem.id.asc(),
        )

    all_items = query.all()

    # Calculate real-time freshness for every item
    results: list[InventoryItemResponse] = []
    for item in all_items:
        freshness = get_freshness_for_item(
            db=db,
            ingredient_id=item.ingredient_id or "",
            storage=item.storage,
            added_on=item.added_on,
            opened_on=item.opened_on,
        )

        if status_filter:
            if freshness.status.value != status_filter.strip().upper():
                continue

        results.append(to_inventory_item_response(item=item, freshness=freshness))

    # Apply pagination limit
    paginated_items = results[:limit]
    next_cursor = None

    return InventoryListResponse(
        items=paginated_items,
        next_cursor=next_cursor,
    )


def get_inventory_item(
    db: Session,
    user: User,
    item_id: uuid.UUID,
) -> InventoryItemResponse:
    """Retrieve a single inventory item by ID scoped to authenticated user."""
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.user_id == user.id,
            InventoryItem.archived_at.is_(None),
        )
        .first()
    )
    if not item:
        raise AppError(
            code="INVENTORY_ITEM_NOT_FOUND",
            message=f"Inventory item '{item_id}' not found.",
            status_code=404,
        )

    freshness = get_freshness_for_item(
        db=db,
        ingredient_id=item.ingredient_id or "",
        storage=item.storage,
        added_on=item.added_on,
        opened_on=item.opened_on,
    )
    return to_inventory_item_response(item=item, freshness=freshness)


def update_inventory_item(
    db: Session,
    user: User,
    item_id: uuid.UUID,
    data: InventoryItemUpdate,
) -> InventoryItemResponse:
    """Update fields on an existing inventory item and recalculate freshness."""
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.user_id == user.id,
            InventoryItem.archived_at.is_(None),
        )
        .first()
    )
    if not item:
        raise AppError(
            code="INVENTORY_ITEM_NOT_FOUND",
            message=f"Inventory item '{item_id}' not found.",
            status_code=404,
        )

    if data.quantity is not None:
        item.quantity = data.quantity
    if data.display_name is not None:
        item.display_name = data.display_name.strip()
    if data.added_on is not None:
        if data.added_on > date.today():
            raise AppError(
                code="INVALID_DATE",
                message="Added date cannot be in the future.",
                status_code=422,
            )
        item.added_on = data.added_on
    if data.storage is not None:
        item.storage = data.storage.strip().upper()
    if data.opened_on is not None:
        item.opened_on = data.opened_on

    # Recalculate freshness
    freshness = get_freshness_for_item(
        db=db,
        ingredient_id=item.ingredient_id or "",
        storage=item.storage,
        added_on=item.added_on,
        opened_on=item.opened_on,
    )
    item.shelf_life_days_estimate = freshness.base_life
    item.expires_on = freshness.expires_on

    # Invalidate recommendation cache (PRD FR-046)
    db.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).delete()

    db.commit()
    db.refresh(item)

    return to_inventory_item_response(item=item, freshness=freshness)


def use_inventory_item(
    db: Session,
    user: User,
    item_id: uuid.UUID,
    quantity_used: Decimal,
) -> InventoryUseResponse:
    """Reduce item quantity and log USED_BEFORE_EXPIRY if status was USE_FIRST or USE_SOON."""
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.user_id == user.id,
            InventoryItem.archived_at.is_(None),
        )
        .first()
    )
    if not item:
        raise AppError(
            code="INVENTORY_ITEM_NOT_FOUND",
            message=f"Inventory item '{item_id}' not found.",
            status_code=404,
        )

    if quantity_used <= 0:
        raise AppError(
            code="INVALID_QUANTITY",
            message="Used quantity must be greater than zero.",
            status_code=422,
        )

    if quantity_used > item.quantity:
        raise AppError(
            code="EXCEEDS_INVENTORY_QUANTITY",
            message=f"Used quantity ({quantity_used}) exceeds current inventory quantity ({item.quantity}).",
            status_code=422,
        )

    freshness = get_freshness_for_item(
        db=db,
        ingredient_id=item.ingredient_id or "",
        storage=item.storage,
        added_on=item.added_on,
        opened_on=item.opened_on,
    )

    action_logged = None
    if freshness.status in (FreshnessStatus.USE_FIRST, FreshnessStatus.USE_SOON):
        action_logged = "USED_BEFORE_EXPIRY"
        ingredient = (
            db.query(Ingredient).filter(Ingredient.id == item.ingredient_id).first()
        )
        estimated_val = (
            calculate_estimated_cost(ingredient, quantity_used, item.unit)
            if ingredient
            else Decimal("0.00")
        )
        waste_entry = WasteLog(
            user_id=user.id,
            inventory_item_id=item.id,
            ingredient_id=item.ingredient_id or "unknown",
            quantity=quantity_used,
            unit=item.unit,
            action=action_logged,
            estimated_value_inr=estimated_val,
        )
        db.add(waste_entry)

    item.quantity -= quantity_used
    is_archived = False
    if item.quantity == 0:
        item.archived_at = datetime.now(timezone.utc)
        is_archived = True

    # Invalidate recommendation cache (PRD FR-046)
    db.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).delete()

    db.commit()
    db.refresh(item)

    return InventoryUseResponse(
        item=to_inventory_item_response(item=item, freshness=freshness),
        action_logged=action_logged,
        quantity_used=quantity_used,
        is_archived=is_archived,
    )


def waste_inventory_item(
    db: Session,
    user: User,
    item_id: uuid.UUID,
    quantity_wasted: Decimal | None = None,
) -> InventoryWasteResponse:
    """Record a WASTED event in waste_log and archive or reduce item quantity."""
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.user_id == user.id,
            InventoryItem.archived_at.is_(None),
        )
        .first()
    )
    if not item:
        raise AppError(
            code="INVENTORY_ITEM_NOT_FOUND",
            message=f"Inventory item '{item_id}' not found.",
            status_code=404,
        )

    qty_to_waste = quantity_wasted if quantity_wasted is not None else item.quantity

    if qty_to_waste <= 0:
        raise AppError(
            code="INVALID_QUANTITY",
            message="Wasted quantity must be greater than zero.",
            status_code=422,
        )

    if qty_to_waste > item.quantity:
        raise AppError(
            code="EXCEEDS_INVENTORY_QUANTITY",
            message=f"Wasted quantity ({qty_to_waste}) exceeds current inventory quantity ({item.quantity}).",
            status_code=422,
        )

    ingredient = (
        db.query(Ingredient).filter(Ingredient.id == item.ingredient_id).first()
    )
    estimated_val = (
        calculate_estimated_cost(ingredient, qty_to_waste, item.unit)
        if ingredient
        else Decimal("0.00")
    )

    waste_entry = WasteLog(
        user_id=user.id,
        inventory_item_id=item.id,
        ingredient_id=item.ingredient_id or "unknown",
        quantity=qty_to_waste,
        unit=item.unit,
        action="WASTED",
        estimated_value_inr=estimated_val,
    )
    db.add(waste_entry)

    item.quantity -= qty_to_waste
    is_archived = False
    if item.quantity == 0:
        item.archived_at = datetime.now(timezone.utc)
        is_archived = True

    freshness = get_freshness_for_item(
        db=db,
        ingredient_id=item.ingredient_id or "",
        storage=item.storage,
        added_on=item.added_on,
        opened_on=item.opened_on,
    )

    # Invalidate recommendation cache (PRD FR-046)
    db.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).delete()

    db.commit()
    db.refresh(item)

    return InventoryWasteResponse(
        item=to_inventory_item_response(item=item, freshness=freshness),
        action_logged="WASTED",
        quantity_wasted=qty_to_waste,
        estimated_value_inr=estimated_val,
        is_archived=is_archived,
    )


def delete_inventory_item(
    db: Session,
    user: User,
    item_id: uuid.UUID,
) -> None:
    """Delete an inventory item belonging to the authenticated user."""
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.user_id == user.id,
        )
        .first()
    )
    if not item:
        raise AppError(
            code="INVENTORY_ITEM_NOT_FOUND",
            message=f"Inventory item '{item_id}' not found.",
            status_code=404,
        )

    db.delete(item)

    # Invalidate recommendation cache (PRD FR-046)
    db.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).delete()

    db.commit()
