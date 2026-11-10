import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.auth import User
from app.db.session import get_db
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryListResponse,
    InventoryUseRequest,
    InventoryUseResponse,
    InventoryWasteRequest,
    InventoryWasteResponse,
)
from app.services.inventory import (
    create_inventory_item,
    delete_inventory_item,
    get_inventory_item,
    list_inventory_items,
    update_inventory_item,
    use_inventory_item,
    waste_inventory_item,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get(
    "",
    response_model=InventoryListResponse,
    status_code=status.HTTP_200_OK,
)
def list_inventory(
    status: str | None = Query(default=None, description="Filter by status (USE_FIRST, USE_SOON, SAFE)"),
    storage: str | None = Query(default=None, description="Filter by storage (FRIDGE, FREEZER, PANTRY, COUNTER)"),
    sort: str = Query(default="expiry", description="Sort by expiry, name, or added"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryListResponse:
    """Retrieve user's active inventory items with real-time freshness estimation."""
    return list_inventory_items(
        db=db,
        user=current_user,
        status_filter=status,
        storage_filter=storage,
        sort_by=sort,
        limit=limit,
        cursor=cursor,
    )


@router.post(
    "",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_inventory_item(
    item_data: InventoryItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryItemResponse:
    """Add a verified ingredient item to the user's inventory with calculated freshness."""
    return create_inventory_item(
        db=db,
        user=current_user,
        data=item_data,
    )


@router.get(
    "/{item_id}",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_200_OK,
)
def get_single_inventory_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryItemResponse:
    """Retrieve details and freshness status of a specific inventory item."""
    return get_inventory_item(
        db=db,
        user=current_user,
        item_id=item_id,
    )


@router.patch(
    "/{item_id}",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_200_OK,
)
def edit_inventory_item(
    item_id: uuid.UUID,
    update_data: InventoryItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryItemResponse:
    """Update inventory item quantity, storage, or opened date and recalculate freshness."""
    return update_inventory_item(
        db=db,
        user=current_user,
        item_id=item_id,
        data=update_data,
    )


@router.post(
    "/{item_id}/use",
    response_model=InventoryUseResponse,
    status_code=status.HTTP_200_OK,
)
def mark_inventory_item_used(
    item_id: uuid.UUID,
    use_data: InventoryUseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryUseResponse:
    """Reduce item quantity and log USED_BEFORE_EXPIRY if item was close to expiry."""
    return use_inventory_item(
        db=db,
        user=current_user,
        item_id=item_id,
        quantity_used=use_data.quantity,
    )


@router.post(
    "/{item_id}/waste",
    response_model=InventoryWasteResponse,
    status_code=status.HTTP_200_OK,
)
def mark_inventory_item_wasted(
    item_id: uuid.UUID,
    waste_data: InventoryWasteRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryWasteResponse:
    """Log food waste and reduce or archive the inventory item."""
    qty_wasted = waste_data.quantity if waste_data else None
    return waste_inventory_item(
        db=db,
        user=current_user,
        item_id=item_id,
        quantity_wasted=qty_wasted,
    )


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_inventory_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete an item from inventory."""
    delete_inventory_item(
        db=db,
        user=current_user,
        item_id=item_id,
    )
