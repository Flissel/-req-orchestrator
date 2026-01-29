"""
Items CRUD endpoint for {{PROJECT_NAME}}.

Example endpoint demonstrating REST operations.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.item import Item

router = APIRouter()


# ----- Schemas -----


class ItemBase(BaseModel):
    """Base schema for Item."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0)
    is_active: bool = Field(default=True)


class ItemCreate(ItemBase):
    """Schema for creating an Item."""

    pass


class ItemUpdate(BaseModel):
    """Schema for updating an Item."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None


class ItemResponse(ItemBase):
    """Schema for Item response."""

    id: UUID
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ----- Endpoints -----


@router.get("", response_model=List[ItemResponse])
async def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> List[Item]:
    """
    List all items with pagination.

    - **skip**: Number of items to skip (default: 0)
    - **limit**: Maximum number of items to return (default: 100)
    """
    result = await db.execute(
        select(Item).offset(skip).limit(limit).order_by(Item.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Item:
    """
    Get a specific item by ID.

    - **item_id**: UUID of the item to retrieve
    """
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )

    return item


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_in: ItemCreate,
    db: AsyncSession = Depends(get_db),
) -> Item:
    """
    Create a new item.

    - **name**: Item name (required)
    - **description**: Item description (optional)
    - **price**: Item price (required, must be > 0)
    - **is_active**: Whether the item is active (default: true)
    """
    item = Item(**item_in.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: UUID,
    item_in: ItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> Item:
    """
    Update an existing item.

    Only provided fields will be updated.
    """
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )

    # Update only provided fields
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an item by ID.

    - **item_id**: UUID of the item to delete
    """
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )

    await db.delete(item)