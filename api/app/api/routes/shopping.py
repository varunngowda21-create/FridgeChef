"""Shopping lists API router per PRD Section 6.7, 8.7, 10, and 11.9."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.auth import User
from app.schemas.shopping import (
    ShoppingItemPatchRequest,
    ShoppingListCreateRequest,
    ShoppingListResponse,
)
from app.services.shopping import (
    create_shopping_list,
    get_shopping_list,
    patch_shopping_item,
)

router = APIRouter(prefix="/shopping-lists", tags=["Shopping Lists"])


@router.post(
    "",
    response_model=ShoppingListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create shopping list",
    description="Creates an aggregated shopping list from a meal plan, recipe selection, or manual entries, subtracting current inventory.",
)
def create_list(
    body: ShoppingListCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShoppingListResponse:
    """Create shopping list."""
    return create_shopping_list(
        db=db,
        user=current_user,
        request=body,
    )


@router.get(
    "/{id}",
    response_model=ShoppingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get shopping list by ID",
    description="Retrieves a specific shopping list by ID (scoped to owner).",
)
def get_by_id(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShoppingListResponse:
    """Retrieve shopping list by ID."""
    return get_shopping_list(db=db, user=current_user, list_id=id)


@router.patch(
    "/{id}/items/{canonical_id}",
    response_model=ShoppingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Update shopping list item bought status",
    description="Marks an item as bought and optionally adds it to user inventory.",
)
def patch_item(
    id: uuid.UUID,
    canonical_id: str,
    body: ShoppingItemPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShoppingListResponse:
    """Update item bought status."""
    return patch_shopping_item(
        db=db,
        user=current_user,
        list_id=id,
        canonical_id=canonical_id,
        request=body,
    )

